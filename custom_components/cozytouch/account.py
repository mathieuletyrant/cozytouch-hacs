"""The Atlantic Cozytouch account a config entry is built on.

One account, one login, one setup view. Everything a Cozytouch account
declares -- the token, the household, the zones, the list of devices -- is the
same answer whatever device is asking, because `setupviewv2` describes the
whole account and not the device that fetched it.

This lived on `Hub`, which meant one config entry per device also bought one
session, one `POST /users/token` and one `GET setupviewv2` per device : a
gateway plus four units cost five logins for four copies of the same payload.
Worse, the state it filled in sat on the `Hub` *class* for a while, so the
hubs overwrote each other and the last one to connect won --
`tests/test_regressions.py` still pins the fix. The state was always shared;
owning it in one object says so, and lets the shape be checked.

The per-device half stays on `Hub` : which capability ids that device reports,
what they mean for its model, and the targeted fetch that confirms a write.
"""

from __future__ import annotations

import asyncio
import copy
from datetime import UTC, datetime
import json
import logging

from aiohttp import ClientError, ClientTimeout, ContentTypeError, FormData

from homeassistant import exceptions
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import COZYTOUCH_ATLANTIC_API, COZYTOUCH_CLIENT_ID
from .model import CozytouchDeviceType, get_model_infos

_LOGGER = logging.getLogger(__name__)

# Timeout for all HTTP requests. Without this, a hung Atlantic API server
# will stall a poll forever, blocking every subsequent one.
REQUEST_TIMEOUT = ClientTimeout(total=30)

# How long to stop asking after a 429 that does not say. Atlantic has never
# been observed sending one -- nothing in the integration used to recognise it
# -- so this is a guess, deliberately long: the cost of waiting five minutes
# too long is stale values, the cost of waiting too little is being throttled
# for good.
RATE_LIMIT_BACKOFF = 300.0

# What a throttling proxy puts in front of its answer. WSO2 API Manager, which
# docs/api-surface.md identifies as the gateway, is the likely source of a 429
# here, and these are the headers that would say what the limit actually is --
# which is the one thing no capture has ever established about `rateLimit`.
# Logged rather than parsed: a reading that comes from a real 429 beats one
# guessed from a number in the setup view.
RATE_LIMIT_HEADERS = (
    "Retry-After",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
)

# What the API declares about a device on top of the fields that drive
# behaviour. Nothing reads these to decide anything: they are carried because a
# diagnostics dump is what a mapping gets built from, and the vendor's own name
# and family for a model the table does not know is the first thing worth
# having. On the one account these were read from, only the gateway carries a
# real longName and a modelFamily -- its children report an internal name or a
# literal "---" -- so what other product families put here is still open.
# docs/api-surface.md has the detail.
API_DECLARED_FIELDS = (
    "longName",
    "modelFamily",
    "productRange",
    "masterDeviceId",
    "isAvailable",
)

# Keys of the setup view worth keeping. The rest of the payload is per-device.
SETUP_FIELDS = (
    "absence",
    "address",
    "area",
    "currency",
    "id",
    "mainDHWEnergy",
    "mainHeatingEnergy",
    "name",
    "numberOfPersons",
    "numberOfRooms",
    # The account's own declared rate limit. Units unknown -- no catalogue
    # decodes it -- so it is carried to the dump rather than acted on; the poll
    # interval is fixed at 60s, comfortably under it on any reading of "30".
    "rateLimit",
    "setupBuildingDate",
    "type",
)

# The subset the away-mode PUT has to send back. `absence` is what the call is
# for and `id` addresses the resource, so neither belongs in the body.
SETUP_WRITABLE_FIELDS = (
    "address",
    "area",
    "currency",
    "mainHeatingEnergy",
    "mainDHWEnergy",
    "name",
    "numberOfPersons",
    "numberOfRooms",
    "setupBuildingDate",
    "type",
)


class CozytouchAccount:
    """One Atlantic account, and the only thing that talks to its API."""

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        """Init the account."""
        self._hass = hass
        # Home Assistant's own session, not one of ours: it is closed when
        # Home Assistant stops, so there is nothing left to leak when a setup
        # fails and the account it built is discarded.
        self._session = async_get_clientsession(hass)
        self._username = username
        self._password = password

        self._access_token = ""
        self._token_expiry: float = 0  # Unix timestamp; 0 = unknown/expired
        # A reconnect is asked for by whoever sees the account offline -- the
        # account poll, or a hub confirming a write -- and the lock is what
        # turns several of them arriving at once into one login.
        self._connect_lock = asyncio.Lock()
        # Set by a 429, and honoured by every caller before it spends a
        # request. 0 = not throttled.
        self._backoff_until: float = 0

        self.online = False
        self.setup: dict = {}
        self.zones: list | dict = []
        self.devices: list = []

        self._dump_json = False

    @property
    def account_id(self) -> str:
        """A stable id for this account, for logging and unique ids."""
        return "cozytouch." + self._username.lower()

    def set_dump_json(self, dump_json: bool) -> None:
        """Set option from the config flow to dump JSON from the API."""
        self._dump_json = dump_json

    def _headers(self) -> dict[str, str]:
        """The authenticated headers every call but the token request uses."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    @property
    def rate_limit(self) -> int | None:
        """What the account declares its own limit to be, if it said.

        The units are still unknown -- docs/api-surface.md has the detail --
        so this is read as requests per minute and only ever as a ceiling,
        which is the most conservative reading the evidence does not contradict.
        """
        rateLimit = self.setup.get("rateLimit")
        return rateLimit if isinstance(rateLimit, int) else None

    @property
    def backoff_remaining(self) -> float:
        """Seconds left before this account may ask Atlantic for anything."""
        return max(0.0, self._backoff_until - datetime.now(UTC).timestamp())

    def _note_rate_limited(self, response, what: str) -> float:
        """Stop asking for a while, and write down everything the 429 said.

        Deliberately does **not** touch `online`. Every other failure here
        drops the connection so the next poll re-authenticates, which for a 429
        is exactly backwards : the token is fine, and reconnecting spends a
        `POST /users/token` and a `GET setupviewv2` on an account that just
        asked for *fewer* requests. Repeated failed logins are also the one
        thing that can lock an account out (docs/api-surface.md), so answering
        a throttle with a login loop is the worst move available.
        """
        retry_after = RATE_LIMIT_BACKOFF
        header = response.headers.get("Retry-After")
        if header:
            try:
                # Seconds, per RFC 9110. It also allows an HTTP-date, which no
                # gateway seen here sends; a value that is not a number falls
                # back to the default rather than throwing inside a poll.
                retry_after = max(0.0, float(header.strip()))
            except ValueError:
                _LOGGER.debug("Unparsed Retry-After: %s", header)

        self._backoff_until = datetime.now(UTC).timestamp() + retry_after

        # At warning level on purpose. Nobody has ever captured a 429 from
        # Atlantic, so the first person to see one is holding the only evidence
        # that would say what `rateLimit: 30` actually counts.
        _LOGGER.warning(
            "Rate limited by Atlantic on %s ; backing off %.0fs. Headers: %s",
            what,
            retry_after,
            {
                name: response.headers[name]
                for name in RATE_LIMIT_HEADERS
                if name in response.headers
            },
        )

        return retry_after

    async def connect(self) -> bool:
        """Log in and read the setup view, unless somebody already did.

        Idempotent on purpose : `online` is the whole reconnect mechanism, and
        every hub on the account flips it and calls this. Re-checking it once
        the lock is held is what keeps a *successful* reconnect from costing
        one login per device -- five coordinators on one beat make one request.

        It does not collapse a failing one : a failure leaves `online` False,
        so each waiter in turn takes the lock, sees that, and tries again.
        That is deliberate for a network failure -- retrying is the answer --
        and wrong for a refused password, which no number of attempts fixes
        and which repeated *failed* logins could get an account locked out
        for (docs/api-surface.md). So `InvalidAuth` is the one exception this
        does **not** fold into `online = False`: it propagates, and
        `connect_or_auth_failed` turns it into the signal that stops the
        retrying rather than scheduling more of it.
        """
        if self.online:
            return True

        # Checked before the lock and before the login : a reconnect is two
        # requests, one of them the kind that locks accounts out, and an
        # account that has just been throttled is the last one to spend them.
        if self.backoff_remaining:
            _LOGGER.debug(
                "Not reconnecting for another %.0fs, rate limited",
                self.backoff_remaining,
            )
            return False

        async with self._connect_lock:
            if self.online:
                return True

            try:
                await self._authenticate()
                await self._read_setup()
                self.online = True
            except CannotConnect:
                self.online = False
            except CozytouchRateLimited:
                # The token was spent and the setup view refused. Nothing to
                # retry now -- the backoff `_note_rate_limited` armed is what
                # keeps the next caller from spending another one.
                self.online = False
            except (TimeoutError, ClientError) as err:
                _LOGGER.warning("connect: network error: %s", err)
                self.online = False

        return self.online

    async def connect_or_auth_failed(self) -> bool:
        """connect(), with a refused password raised rather than returned.

        `ConfigEntryAuthFailed` is what Home Assistant acts on : it opens the
        reauth dialog, and `_async_refresh` stops rescheduling the coordinator
        that raised it -- which is what turns "retry the rejected password
        every minute for as long as the installation runs" into "ask once".

        The two callers -- setup and the poll -- differ only in what they make
        of a plain False, so the translation that has to be identical lives
        here and the retry semantics stay with them.
        """
        try:
            return await self.connect()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(
                "Atlantic Cozytouch rejected the stored credentials"
            ) from err

    async def _authenticate(self) -> None:
        """POST /users/token, and remember when it stops being good."""
        async with self._session.post(
            COZYTOUCH_ATLANTIC_API + "/users/token",
            data=FormData(
                {
                    "grant_type": "password",
                    "scope": "openid",
                    "username": "GA-PRIVATEPERSON/" + self._username,
                    "password": self._password,
                }
            ),
            headers={
                "Authorization": f"Basic {COZYTOUCH_CLIENT_ID}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=REQUEST_TIMEOUT,
        ) as response:
            token = await response.json()

            # The one answer that means the credentials are wrong. OAuth2
            # spells it invalid_grant and Atlantic uses the standard spelling.
            # Anything else malformed is a bad response, not a bad password:
            # telling somebody their password is wrong because the gateway
            # hiccuped sends them off to reset a password that was fine.
            if token.get("error") == "invalid_grant":
                raise InvalidAuth

            if "token_type" not in token:
                raise CannotConnect

            if "access_token" not in token:
                raise CannotConnect

            self._access_token = token["access_token"]
            # Track token expiry; fall back to 1 hour if not provided
            expires_in = token.get("expires_in", 3600)
            self._token_expiry = datetime.now(UTC).timestamp() + expires_in - 60

    async def _read_setup(self) -> None:
        """GET setupviewv2, which is everything the integration knows."""
        async with self._session.get(
            COZYTOUCH_ATLANTIC_API + "/magellan/cozytouch/setupviewv2",
            headers=self._headers(),
            timeout=REQUEST_TIMEOUT,
        ) as response:
            # Not CannotConnect, which `connect()` and `refresh_setup` both
            # answer by dropping `online` -- the very reconnect a 429 must not
            # provoke. It has to stay distinguishable all the way up.
            if response.status == 429:
                retry_after = self._note_rate_limited(response, "the setup view")
                raise CozytouchRateLimited(
                    "Rate limited by the setup view", retry_after
                )

            json_data = await response.json()

            # An empty list or an error dict would blow up on json_data[0]
            # below; treat it as a failed connection so setup is retried
            if not isinstance(json_data, list) or not json_data:
                _LOGGER.warning(
                    "connect: unexpected setup payload (%s)",
                    type(json_data).__name__,
                )
                raise CannotConnect

            for key in SETUP_FIELDS:
                if key in json_data[0]:
                    self.setup[key] = copy.deepcopy(json_data[0][key])

            # Update devices infos
            await asyncio.get_event_loop().run_in_executor(
                None, self.update_devices_from_json_data, json_data
            )

    async def refresh_setup(self) -> None:
        """Re-read the setup view, which is the poll.

        The same request `connect()` makes, called on a beat rather than once :
        it carries a capability list for **every** device on the account
        (`update_devices_from_json_data` keeps all of them), so one request
        refreshes the whole account where the per-device route refreshes one
        device. It also carries `absence`, which lives nowhere else -- an away
        window set in the Cozytouch app used to wait for a reconnect to be
        seen.

        What it does not carry is proof of being as fresh as
        `/magellan/capabilities/`. The two are the same three fields
        (docs/api-surface.md) and the integration has always built its entities
        from this payload at startup, but nobody has compared their latency.
        `modificationDate` is in both and read by neither, so the measurement
        is there to be made -- `scripts/probe_api.py --cadence` makes it.
        """
        if self.backoff_remaining:
            raise CozytouchRateLimited(
                "Still backing off from a 429", self.backoff_remaining
            )

        try:
            await self._read_setup()
        except CannotConnect as err:
            self.online = False
            raise CozytouchApiError("Unusable setup view, forcing reconnect") from err
        except (TimeoutError, ClientError) as err:
            self.online = False
            raise CozytouchApiError(
                f"Network error reading the setup view: {err}, forcing reconnect"
            ) from err

    def check_token(self) -> None:
        """Drop the connection when the token is spent, so the next poll re-auths.

        There is no separate retry loop anywhere : flipping `online` is how
        every failure path here asks for a reconnect, and an expiry is just
        another one, seen a minute early.
        """
        if self.online and datetime.now(UTC).timestamp() >= self._token_expiry:
            _LOGGER.info("Token expired or about to expire, re-authenticating")
            self.online = False

    def update_devices_from_json_data(self, json_data) -> None:
        """Update the devices list."""
        if self._dump_json:
            with open(
                self._hass.config.config_dir + "/Cozytouch.json", "w", encoding="utf-8"
            ) as outfile:
                json_object = json.dumps(json_data, indent=4)
                outfile.write(json_object)

        # Refreshed on every setup view, not just the first: renaming a zone in
        # the Cozytouch app has to reach the entity names it feeds.
        if "zones" in json_data[0]:
            self.zones = copy.deepcopy(json_data[0]["zones"])

        # Start by removing old devices
        for local_device in self.devices[:]:
            bStillExists = False
            for remote_device in json_data[0]["devices"]:
                if remote_device["deviceId"] == local_device["deviceId"]:
                    bStillExists = True
                    break

            if bStillExists is False:
                self.devices.remove(local_device)

        # Create new devices
        deviceIndex = -1
        for remote_device in json_data[0]["devices"]:
            deviceIndex = -1
            for i, local_device in enumerate(self.devices):
                if remote_device["deviceId"] == local_device["deviceId"]:
                    deviceIndex = i
                    break

            if deviceIndex == -1:
                device = {
                    "deviceId": remote_device["deviceId"],
                    "name": remote_device["name"],
                    "gatewaySerialNumber": remote_device["gatewaySerialNumber"],
                    "modelId": remote_device["modelId"],
                    "productId": remote_device["productId"],
                    "zoneId": remote_device["zoneId"],
                    "modelInfos": get_model_infos(remote_device["modelId"]),
                    "capabilities": [],
                    "tags": [],
                }
                if "tags" in remote_device:
                    device["tags"] = copy.deepcopy(remote_device["tags"])

                self.devices.append(device)
                deviceIndex = len(self.devices) - 1

            # Refreshed on every setup view rather than set once at creation:
            # isAvailable moves as a device drops off the gateway, and a device
            # renamed in the app should not keep its old longName.
            for field in API_DECLARED_FIELDS:
                self.devices[deviceIndex][field] = remote_device.get(field)

            # Every device, not just the one that asked. The setup view carries
            # capabilities for all of them and this used to drop all but one,
            # which cost the account a per-device poll before its entities could
            # be built -- and left a diagnostics dump describing the hardware
            # nobody has mapped yet without the capability ids that are the
            # whole point of the dump.
            if "capabilities" in remote_device:
                self.devices[deviceIndex]["capabilities"] = copy.deepcopy(
                    remote_device["capabilities"]
                )

    async def fetch_capabilities(self, deviceId: int) -> list:
        """GET the capability list of one device.

        No longer the beat -- `refresh_setup` is, and it covers every device at
        once. This is what confirms a write on the device that was written to,
        where re-reading the whole household to check one setpoint would be
        absurd.

        Raises rather than returning a sentinel : the caller is a coordinator,
        and an empty list is a legitimate answer that must not read as a
        failure. Every failure but a 429 also drops `online`, which is what
        asks for the reconnect.
        """
        if self.backoff_remaining:
            raise CozytouchRateLimited(
                "Still backing off from a 429", self.backoff_remaining
            )

        try:
            async with self._session.get(
                COZYTOUCH_ATLANTIC_API
                + "/magellan/capabilities/?deviceId="
                + str(deviceId),
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT,
            ) as response:
                # 401 means the token was rejected; force re-auth next poll
                if response.status == 401:
                    self.online = False
                    raise CozytouchApiError(
                        "Token rejected (401), forcing re-authentication next poll"
                    )

                # Before the generic branch below, and without dropping the
                # session : a 429 is the one status that must not be answered
                # with a reconnect.
                if response.status == 429:
                    retry_after = self._note_rate_limited(response, "the capabilities")
                    raise CozytouchRateLimited(
                        "Rate limited by the capabilities endpoint", retry_after
                    )

                if response.status != 200:
                    self.online = False
                    raise CozytouchApiError(
                        f"Unexpected status {response.status} from"
                        " capabilities endpoint"
                    )

                try:
                    json_data = await response.json()
                except ContentTypeError as err:
                    self.online = False
                    raise CozytouchApiError(
                        "Non-JSON response from capabilities endpoint"
                    ) from err

                if not isinstance(json_data, list):
                    self.online = False
                    raise CozytouchApiError(
                        "Capabilities response is not a list (got"
                        f" {type(json_data).__name__}), forcing reconnect"
                    )

                return json_data

        except TimeoutError as err:
            self.online = False
            raise CozytouchApiError(
                f"Timeout fetching capabilities for device {deviceId},"
                " forcing reconnect"
            ) from err
        except ClientError as err:
            self.online = False
            raise CozytouchApiError(
                "Network error fetching capabilities for device"
                f" {deviceId}: {err}, forcing reconnect"
            ) from err

    def store_capabilities(self, deviceId: int, capabilities: list) -> None:
        """Put a freshly polled capability list back on the device."""
        for dev in self.devices:
            if dev["deviceId"] == deviceId:
                dev["capabilities"] = copy.deepcopy(capabilities)
                break

    async def write_capability(
        self, deviceId: int, capabilityId: int, value: str
    ) -> bool:
        """Write one capability, and wait for the execution to complete.

        A write is not fire-and-forget : the POST answers with an execution id,
        and the state of that execution is polled -- once immediately, then up
        to five more times a second apart -- until it reports 3. Returning
        False means the local value must stay as it was, and the next poll will
        say what actually happened.

        Attempted even while the account is backing off from a 429, unlike the
        polls : somebody just pressed a button, and refusing to send it because
        a *reader* was throttled would be a worse answer than letting the
        server refuse it. A 429 here still arms the backoff, so the readers
        learn from a write's rejection.
        """
        try:
            async with self._session.post(
                COZYTOUCH_ATLANTIC_API + "/magellan/executions/writecapability",
                json={
                    "capabilityId": capabilityId,
                    "deviceId": deviceId,
                    "value": value,
                },
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status == 429:
                    self._note_rate_limited(response, "a capability write")
                    return False

                if response.status != 201:
                    return False

                executionId = await response.json()
        except (TimeoutError, ClientError) as err:
            _LOGGER.warning(
                "Network error writing capability %d: %s", capabilityId, err
            )
            return False

        return await self._await_execution(executionId)

    async def _await_execution(self, executionId) -> bool:
        """Poll one execution until it reports completion, or give up."""
        nbRetry = 0
        while True:
            try:
                async with self._session.get(
                    COZYTOUCH_ATLANTIC_API + "/magellan/executions/" + str(executionId),
                    headers=self._headers(),
                    timeout=REQUEST_TIMEOUT,
                ) as response:
                    # This loop is the burstiest thing the integration does --
                    # up to six requests in five seconds for one button press
                    # -- so it is the likeliest place to meet the limit, and
                    # the last place to keep hammering after meeting it.
                    if response.status == 429:
                        self._note_rate_limited(response, "an execution poll")
                        return False

                    try:
                        execution_data = await response.json()
                    except ContentTypeError:
                        self.online = False
                        return False

                    execution_state = execution_data.get("state", False)
                    if execution_state == 1:
                        _LOGGER.info("Execution_state waiting execution")
                    elif execution_state == 2:
                        _LOGGER.info("Execution_state in progress")
                    elif execution_state == 3:
                        _LOGGER.info("Execution_state completed")
                        return True
                    else:
                        _LOGGER.info("Execution_state error")
                        return False
            except (TimeoutError, ClientError) as err:
                _LOGGER.warning("Network error polling execution: %s", err)
                return False

            nbRetry += 1
            if nbRetry > 5:
                return False

            await asyncio.sleep(1)

    async def set_absence(self, timestampStart, timestampEnd) -> bool:
        """PUT the absence window on the setup.

        Away mode is the one feature that is not a capability write alone : the
        window lives on the setup, a resource of the account rather than of a
        device, which is why it is here and not on the hub.
        """
        json_data = {
            key: copy.deepcopy(self.setup[key])
            for key in SETUP_WRITABLE_FIELDS
            if key in self.setup
        }

        json_data["absence"] = {}
        if timestampStart is not None and timestampEnd is not None:
            json_data["absence"]["startDate"] = timestampStart
            json_data["absence"]["endDate"] = timestampEnd

        try:
            async with self._session.put(
                COZYTOUCH_ATLANTIC_API + "/magellan/v2/setups/" + str(self.setup["id"]),
                json=json_data,
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status in (200, 204):
                    return True

                if response.status == 429:
                    self._note_rate_limited(response, "the absence window")
                    return False

                _LOGGER.error(
                    "Set away mode : response %d (%s)",
                    response.status,
                    str(response.request_info),
                )
        except (TimeoutError, ClientError) as err:
            _LOGGER.warning("Network error writing the absence window: %s", err)

        return False

    def device_summaries(self) -> list[dict]:
        """The devices as a config flow needs to list them."""
        return [
            {
                "deviceId": dev["deviceId"],
                "name": dev["name"],
                "model": dev["modelInfos"]["name"],
            }
            for dev in self.devices
        ]

    def get_zone_name(self, zoneId: int | None) -> str:
        """Get zone infos."""
        for zone in self.zones:
            if "id" in zone and zone["id"] == zoneId:
                return zone["name"]

        return str(zoneId)

    def get_unmapped_models(self) -> list[int]:
        """Every model id on the account the table has no branch for.

        The whole account rather than one device : the setup view lists them
        all, and one report that covers everything is one issue for the person
        who has to write it, instead of one per device.
        """
        unmapped = {
            dev["modelId"]
            for dev in self.devices
            if get_model_infos(dev["modelId"])["type"] is CozytouchDeviceType.UNKNOWN
        }

        return sorted(unmapped)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate the account refused the username and password.

    Distinct from CannotConnect because the two want opposite handling:
    CannotConnect is retried until the network comes back, InvalidAuth never
    resolves without somebody typing a new password.
    """


class CozytouchApiError(exceptions.HomeAssistantError):
    """Error to indicate a call to the Cozytouch API did not answer usefully."""


class CozytouchRateLimited(CozytouchApiError):
    """Error to indicate Atlantic asked for fewer requests, not for none.

    A subclass, so a caller that only cares that the call failed keeps
    working. What it adds is `retry_after` and, more importantly, what it does
    *not* do : unlike every other failure here it leaves `online` alone,
    because the session is fine and reconnecting would spend two more requests
    answering a complaint about spending requests.
    """

    def __init__(self, message: str, retry_after: float) -> None:
        """Init with how long the server, or the default, asks us to wait."""
        super().__init__(message)
        self.retry_after = retry_after
