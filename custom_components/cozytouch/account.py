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
what they mean for its model, and the 60-second poll that refreshes them.
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
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import COZYTOUCH_ATLANTIC_API, COZYTOUCH_CLIENT_ID
from .model import CozytouchDeviceType, get_model_infos

_LOGGER = logging.getLogger(__name__)

# Timeout for all HTTP requests. Without this, a hung Atlantic API server
# will stall a poll forever, blocking every subsequent one.
REQUEST_TIMEOUT = ClientTimeout(total=30)

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
        # Every hub of this account calls connect() the moment it sees the
        # account offline, and they all poll on the same 60-second beat. The
        # lock is what turns five simultaneous reconnects into one login.
        self._connect_lock = asyncio.Lock()

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

    async def connect(self) -> bool:
        """Log in and read the setup view, unless somebody already did.

        Idempotent on purpose : `online` is the whole reconnect mechanism, and
        every hub on the account flips it and calls this. Re-checking it once
        the lock is held is what keeps that from costing one login per device
        -- repeated *failed* logins are the one thing that could lock an
        account out (docs/api-surface.md).
        """
        if self.online:
            return True

        async with self._connect_lock:
            if self.online:
                return True

            try:
                await self._authenticate()
                await self._read_setup()
                self.online = True
            except CannotConnect:
                self.online = False
            except (TimeoutError, ClientError) as err:
                _LOGGER.warning("connect: network error: %s", err)
                self.online = False

        return self.online

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

            if "error" in token and token["error"] == "invalid_grant":
                raise CannotConnect

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
        """GET the capability list of one device, the 60-second poll.

        Raises rather than returning a sentinel : the caller is a coordinator,
        and an empty list is a legitimate answer that must not read as a
        failure. Every failure also drops `online`, which is what asks for the
        reconnect.
        """
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


class CozytouchApiError(exceptions.HomeAssistantError):
    """Error to indicate a call to the Cozytouch API did not answer usefully."""
