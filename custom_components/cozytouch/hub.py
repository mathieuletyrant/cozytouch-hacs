"""Atlantic Cozytouch Hub."""

from __future__ import annotations

import asyncio
import copy
from datetime import UTC, datetime, timedelta
import json
import logging

from aiohttp import ClientError, ClientSession, ClientTimeout, ContentTypeError, FormData

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .capability import get_capability_infos
from .const import COZYTOUCH_ATLANTIC_API, COZYTOUCH_CLIENT_ID, DOMAIN
from .model import CozytouchDeviceType, get_model_infos

_LOGGER = logging.getLogger(__name__)

# Timeout for all HTTP requests. Without this, a hung Atlantic API server
# will stall _async_update_data forever, blocking all subsequent polls.
REQUEST_TIMEOUT = ClientTimeout(total=30)

# How often the coordinator asks Atlantic for a device's capabilities.
POLL_INTERVAL = timedelta(seconds=60)

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


# A config entry that carries its hub, so platforms can read it off the entry
# instead of looking it up in hass.data by id.
type CozytouchConfigEntry = ConfigEntry[Hub]


class Hub(DataUpdateCoordinator):
    """Atlantic Cozytouch Hub."""

    manufacturer = "Atlantic Group"

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        deviceId: int | None = None,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Init hub."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Cozytouch_" + str(deviceId),
            update_interval=POLL_INTERVAL,
        )
        # Per-account state. These used to sit on the class, where one dict was
        # shared by every hub: an account with one config entry per device --
        # a gateway plus a room unit per zone -- had them all writing over each
        # other's setup, and the last one to connect won.
        self._setup: dict = {}
        self._zones: list | dict = {}

        self._timestamp_away_mode_last_change = None
        self._timestamp_away_mode_start = None
        self._timestamp_away_mode_end = None

        self._session = ClientSession()
        self._host = "none"
        self._hass = hass
        self._username = username
        self._password = password
        self._deviceId = deviceId
        self._zoneId = -1
        self._access_token = ""
        self._id = "cozytouch." + username.lower()
        self._create_unknown = False
        self._dump_json = False
        self._devices = []

        self.online = False
        self._token_expiry: float = 0  # Unix timestamp; 0 = unknown/expired

        modelInfos = self.get_model_infos()
        if "name" in modelInfos:
            self.device_info = DeviceInfo(
                entry_type=DeviceEntryType.SERVICE,
                identifiers={("cozytouch", "cozytouch" + str(deviceId))},
                manufacturer="Atlantic",
                name=modelInfos["name"],
            )

        self._timestamps_away_mode_capability_id = None

    @property
    def hub_id(self) -> str:
        """ID for hub."""
        return self._id

    async def test_connection(self) -> bool:
        """Test connection."""
        await self.connect()
        return self.online

    async def connect(self) -> bool:
        """Connect to Cozytouch server."""
        if self.online is False:
            try:
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

                headers = {
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                }
                async with self._session.get(
                    COZYTOUCH_ATLANTIC_API + "/magellan/cozytouch/setupviewv2",
                    headers=headers,
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

                    # Store setup
                    for key in (
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
                        # The account's own declared rate limit. Units unknown
                        # -- no catalogue decodes it -- so it is carried to the
                        # dump rather than acted on; the poll interval is fixed
                        # at 60s, comfortably under it on any reading of "30".
                        "rateLimit",
                        "setupBuildingDate",
                        "type",
                    ):
                        if key in json_data[0]:
                            self._setup[key] = copy.deepcopy(json_data[0][key])

                    # Update devices infos
                    await asyncio.get_event_loop().run_in_executor(
                        None, self.update_devices_from_json_data, json_data
                    )

                self.online = True

            except CannotConnect:
                self.online = False
            except (ClientError, asyncio.TimeoutError) as err:
                _LOGGER.warning("connect: network error: %s", err)
                self.online = False

        return self.online

    async def close(self) -> None:
        """Close session."""
        await self._session.close()

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
            self._zones = copy.deepcopy(json_data[0]["zones"])

        # Start by removing old devices
        for local_device in self._devices[:]:
            bStillExists = False
            for remote_device in json_data[0]["devices"]:
                if remote_device["deviceId"] == local_device["deviceId"]:
                    bStillExists = True
                    break

            if bStillExists is False:
                self._devices.remove(local_device)

        # Create new devices
        deviceIndex = -1
        for remote_device in json_data[0]["devices"]:
            deviceIndex = -1
            for i, local_device in enumerate(self._devices):
                if remote_device["deviceId"] == local_device["deviceId"]:
                    deviceIndex = i
                    self._zoneId = remote_device["zoneId"]
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

                self._devices.append(device)
                deviceIndex = len(self._devices) - 1

            # Refreshed on every setup view rather than set once at creation:
            # isAvailable moves as a device drops off the gateway, and a device
            # renamed in the app should not keep its old longName.
            for field in API_DECLARED_FIELDS:
                self._devices[deviceIndex][field] = remote_device.get(field)

            # Only retrieve capabilites from current device
            if self._deviceId == remote_device["deviceId"]:
                self._devices[deviceIndex]["capabilities"] = copy.deepcopy(
                    remote_device["capabilities"]
                )

    def set_create_entities_for_unknown_entities(self, create_unknown: bool) -> None:
        """Set option from config flow to create entities for unknown capabilities."""
        self._create_unknown = create_unknown

    def get_create_entities_for_unknown_entities(self) -> bool:
        """Get option from config flow to create entities for unknown capabilities."""
        return self._create_unknown

    def set_dump_json(self, dump_json: bool) -> None:
        """Set option from config flow to dump JSON from API."""
        self._dump_json = dump_json

    async def _async_update_data(self):
        _LOGGER.debug("_async_update_data %d", self._deviceId)

        # Proactively re-authenticate if the token is about to expire
        if self.online and datetime.now(UTC).timestamp() >= self._token_expiry:
            _LOGGER.info("Token expired or about to expire, re-authenticating")
            self.online = False

        if self.online:
            try:
                headers = {
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                }
                async with self._session.get(
                    COZYTOUCH_ATLANTIC_API
                    + "/magellan/capabilities/?deviceId="
                    + str(self._deviceId),
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                ) as response:
                    # 401 means the token was rejected; force re-auth next poll
                    if response.status == 401:
                        self.online = False
                        raise UpdateFailed(
                            "Token rejected (401), forcing re-authentication next poll"
                        )

                    if response.status != 200:
                        self.online = False
                        raise UpdateFailed(
                            f"Unexpected status {response.status} from capabilities endpoint"
                        )

                    try:
                        json_data = await response.json()
                    except ContentTypeError as err:
                        self.online = False
                        raise UpdateFailed(
                            "Non-JSON response from capabilities endpoint"
                        ) from err

                    if isinstance(json_data, list):
                        for dev in self._devices:
                            if dev["deviceId"] == self._deviceId:
                                dev["capabilities"] = copy.deepcopy(json_data)
                                break

                        if (
                            self._timestamp_away_mode_last_change is not None
                            and self._timestamps_away_mode_capability_id is not None
                            and self._timestamp_away_mode_start is not None
                            and self._timestamp_away_mode_end is not None
                        ):
                            now = datetime.now(tz=dt_util.DEFAULT_TIME_ZONE).timestamp()
                            if now - self._timestamp_away_mode_last_change > 20:
                                await self.set_away_mode_timestamps(
                                    None,
                                    None,
                                    self._timestamps_away_mode_capability_id,
                                    self._timestamp_away_mode_start,
                                    self._timestamp_away_mode_end,
                                )
                    else:
                        self.online = False
                        raise UpdateFailed(
                            f"Capabilities response is not a list (got {type(json_data).__name__}), forcing reconnect"
                        )

            except asyncio.TimeoutError as err:
                self.online = False
                raise UpdateFailed(
                    f"Timeout fetching capabilities for device {self._deviceId}, forcing reconnect"
                ) from err
            except ClientError as err:
                self.online = False
                raise UpdateFailed(
                    f"Network error fetching capabilities for device {self._deviceId}: {err}, forcing reconnect"
                ) from err

        else:
            await self.connect()
            if not self.online:
                raise UpdateFailed("Cannot connect to Atlantic Cozytouch API")

    def devices(self):
        """Get devices list."""
        devs = []
        for dev in self._devices:
            devs.append(
                {
                    "deviceId": dev["deviceId"],
                    "name": dev["name"],
                    "model": dev["modelInfos"]["name"],
                }
            )

        return devs

    def get_zone_name(self, zoneId: int | None = None) -> str:
        """Get zone infos."""
        if not zoneId:
            zoneId = self._zoneId

        for zone in self._zones:
            if "id" in zone and zone["id"] == zoneId:
                return zone["name"]

        return str(zoneId)

    def get_model_infos(self, deviceId: int | None = None) -> str:
        """Get model infos."""
        if not deviceId:
            deviceId = self._deviceId

        for dev in self._devices:
            if dev["deviceId"] == deviceId:
                zoneId = dev["zoneId"]

                # Special case for sub-devices, use master zone Id
                for masterDev in self._devices:
                    if "tags" in masterDev:
                        for tag in masterDev["tags"]:
                            if (
                                "label" in tag
                                and tag["label"] == "iothubChildrenIds"
                                and "value" in tag
                                and tag["value"] == dev["name"]
                            ):
                                zoneId = masterDev["zoneId"]
                                break

                return get_model_infos(dev["modelId"], self.get_zone_name(zoneId))

        return get_model_infos(-1)

    def get_serial_number(self, deviceId: int | None = None) -> str:
        """Get serial number."""
        if not deviceId:
            deviceId = self._deviceId

        for dev in self._devices:
            if dev["deviceId"] == deviceId:
                return dev["gatewaySerialNumber"]

        return "Unknown"

    def get_via_device(self, deviceId: int | None = None) -> tuple[str, str] | None:
        """Identifiers of the gateway this device hangs off, when HA has it.

        The API declares the topology itself: every room unit and thermal zone
        on the account carries the gateway's id in masterDeviceId. Home
        Assistant can only draw the link if the gateway was set up too, since a
        device here is registered under its own config entry id -- so this
        returns None for a gateway, and for a child whose gateway nobody added.

        None rather than a guess matters: HA logs a warning when via_device
        names a device that is not in the registry.
        """
        if not deviceId:
            deviceId = self._deviceId

        masterDeviceId = None
        for dev in self._devices:
            if dev["deviceId"] == deviceId:
                masterDeviceId = dev.get("masterDeviceId")
                break

        if not masterDeviceId:
            return None

        for entry in self._hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("deviceId") == masterDeviceId:
                return (DOMAIN, entry.entry_id)

        return None

    def get_capabilities_for_device(self, deviceId: int | None = None):
        """Get capabilities for a device."""

        if not deviceId:
            deviceId = self._deviceId

        capabilities = []
        for dev in self._devices:
            if dev["deviceId"] == deviceId:
                modelInfos = get_model_infos(dev["modelId"])
                availableCapabilityIds = {
                    cap["capabilityId"] for cap in dev["capabilities"]
                }
                for capability in dev["capabilities"]:
                    capability_infos = get_capability_infos(
                        modelInfos,
                        capability["capabilityId"],
                        capability["value"],
                        availableCapabilityIds,
                    )

                    if capability_infos is None and self._create_unknown:
                        capability_infos = {
                            "capabilityId": capability["capabilityId"],
                            "name": "Capability_" + str(capability["capabilityId"]),
                            "type": "string",
                            "category": "diag",
                        }

                    if capability_infos is not None and len(capability_infos) > 0:
                        capability_infos["deviceId"] = deviceId

                        isDuplicate = False
                        if "capabilityDuplicate" in capability_infos:
                            for cap in capabilities:
                                if (
                                    cap["capabilityId"]
                                    == capability_infos["capabilityDuplicate"]
                                ):
                                    isDuplicate = True
                                    break

                        if not isDuplicate:
                            capabilities.append(capability_infos)

        return capabilities

    def get_diagnostics(self) -> dict:
        """Describe the account as the API reports it, for a diagnostics dump.

        Every device the setup returns is listed, whether or not this config
        entry drives it, because what a mapping needs first is the model ids a
        user actually owns. Capabilities are only held for the entry's own
        device -- update_devices_from_json_data drops the others -- so the rest
        carry a null capability block rather than an empty one that would read
        as "reports nothing".
        """
        devices = []
        for dev in self._devices:
            modelInfos = get_model_infos(dev["modelId"])
            entry_owns_it = dev["deviceId"] == self._deviceId

            capabilities = None
            if entry_owns_it:
                availableCapabilityIds = {
                    cap["capabilityId"] for cap in dev["capabilities"]
                }
                mapped, unmapped = {}, []
                for cap in dev["capabilities"]:
                    infos = get_capability_infos(
                        modelInfos,
                        cap["capabilityId"],
                        cap["value"],
                        availableCapabilityIds,
                    )
                    if infos:
                        mapped[cap["capabilityId"]] = infos.get("name")
                    else:
                        unmapped.append(cap["capabilityId"])

                capabilities = {
                    "mapped": mapped,
                    "unmapped": sorted(unmapped),
                    "values": {
                        cap["capabilityId"]: cap["value"] for cap in dev["capabilities"]
                    },
                }

            devices.append(
                {
                    "deviceId": dev["deviceId"],
                    "name": dev["name"],
                    "modelId": dev["modelId"],
                    "productId": dev["productId"],
                    "zoneId": dev["zoneId"],
                    "zoneName": self.get_zone_name(dev["zoneId"]),
                    "tags": dev["tags"],
                    "isConfiguredHere": entry_owns_it,
                    # Straight from the API, under the API's own names, so a
                    # report can be compared against docs/api-surface.md
                    # without a translation step.
                    **{field: dev.get(field) for field in API_DECLARED_FIELDS},
                    "model": {
                        "name": modelInfos["name"],
                        "type": str(modelInfos["type"]),
                        "isMapped": modelInfos["type"]
                        is not CozytouchDeviceType.UNKNOWN,
                        "infos": {
                            key: str(value)
                            for key, value in modelInfos.items()
                            if key not in ("name", "type")
                        },
                    },
                    "capabilities": capabilities,
                }
            )

        return {
            "setup": copy.deepcopy(self._setup),
            "zones": copy.deepcopy(self._zones),
            "devices": devices,
        }

    def get_capability_value(
        self, capabilityId: int, defaultIfNotExist: str | None = "0"
    ):
        """Get value for a device capability."""
        for dev in self._devices:
            if dev["deviceId"] == self._deviceId:
                for capability in dev["capabilities"]:
                    if capabilityId == capability["capabilityId"]:
                        return capability["value"]

                return defaultIfNotExist

        return None

    async def set_capability_value(self, capabilityId: int, value: str):
        """Set value for a device capability."""
        _LOGGER.debug(
            "Set_capability_value for %d : %d = %s", self._deviceId, capabilityId, value
        )
        if self.online:
            for dev in self._devices:
                if dev["deviceId"] == self._deviceId:
                    for capability in dev["capabilities"]:
                        if capabilityId == capability["capabilityId"]:
                            try:
                                # Write capability value
                                async with self._session.post(
                                    COZYTOUCH_ATLANTIC_API
                                    + "/magellan/executions/writecapability",
                                    json={
                                        "capabilityId": capabilityId,
                                        "deviceId": self._deviceId,
                                        "value": value,
                                    },
                                    headers={
                                        "Authorization": f"Bearer {self._access_token}",
                                        "Content-Type": "application/json",
                                    },
                                    timeout=REQUEST_TIMEOUT,
                                ) as response:
                                    if response.status == 201:
                                        # Check completion
                                        executionId = await response.json()
                                        completed = False
                                        nbRetry = 0
                                        while not completed:
                                            async with self._session.get(
                                                COZYTOUCH_ATLANTIC_API
                                                + "/magellan/executions/"
                                                + str(executionId),
                                                headers={
                                                    "Authorization": f"Bearer {self._access_token}",
                                                    "Content-Type": "application/json",
                                                },
                                                timeout=REQUEST_TIMEOUT,
                                            ) as executionResponse:
                                                try:
                                                    execution_data = (
                                                        await executionResponse.json()
                                                    )
                                                    execution_state = (
                                                        execution_data.get(
                                                            "state", False
                                                        )
                                                    )
                                                    if execution_state == 1:
                                                        _LOGGER.info(
                                                            "Execution_state waiting execution"
                                                        )
                                                    elif execution_state == 2:
                                                        _LOGGER.info(
                                                            "Execution_state in progress"
                                                        )
                                                    elif execution_state == 3:
                                                        _LOGGER.info(
                                                            "Execution_state completed"
                                                        )
                                                        completed = True
                                                        break
                                                    else:
                                                        _LOGGER.info(
                                                            "Execution_state error"
                                                        )
                                                        break

                                                except ContentTypeError:
                                                    self.online = False
                                                    break

                                            nbRetry += 1
                                            if nbRetry > 5:
                                                break

                                            await asyncio.sleep(1)

                                        if completed:
                                            capability["value"] = value
                            except (ClientError, asyncio.TimeoutError) as err:
                                _LOGGER.warning(
                                    "Network error writing capability %d: %s",
                                    capabilityId,
                                    err,
                                )
                            break

    def away_mode_init(self, timestampStart, timestampEnd):
        """Init away mode timestamps."""
        self._timestamp_away_mode_start = timestampStart
        self._timestamp_away_mode_end = timestampEnd

    async def set_away_mode_start(
        self,
        capabilityIdTimestamps: int,
        timestamp,
    ):
        """Set away mode start timestamp."""
        self._timestamp_away_mode_start = timestamp
        self._timestamps_away_mode_capability_id = capabilityIdTimestamps
        self._timestamp_away_mode_last_change = datetime.now(
            tz=dt_util.DEFAULT_TIME_ZONE
        ).timestamp()

    def get_away_mode_start(self):
        """Get away mode start timestamp."""
        return self._timestamp_away_mode_start

    async def set_away_mode_end(
        self,
        capabilityIdTimestamps: int,
        timestamp,
    ):
        """Set away mode end timestamp."""
        self._timestamp_away_mode_end = timestamp
        self._timestamps_away_mode_capability_id = capabilityIdTimestamps
        self._timestamp_away_mode_last_change = datetime.now(
            tz=dt_util.DEFAULT_TIME_ZONE
        ).timestamp()

    def get_away_mode_end(self):
        """Get away mode end timestamp."""
        return self._timestamp_away_mode_end

    async def set_away_mode_timestamps(
        self,
        capabilityIdMode,
        valueMode,
        capabilityIdTimestamps: int,
        timestampStart,
        timestampEnd,
    ):
        """Set away mode timestamps."""

        if self.online:
            # Update setup
            json_data = {}
            for key in (
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
            ):
                if key in self._setup:
                    json_data[key] = copy.deepcopy(self._setup[key])

            json_data["absence"] = {}
            if timestampStart is not None and timestampEnd is not None:
                json_data["absence"]["startDate"] = timestampStart
                json_data["absence"]["endDate"] = timestampEnd
                _timestamp_away_mode_start = timestampStart
                _timestamp_away_mode_end = timestampEnd

            async with self._session.put(
                COZYTOUCH_ATLANTIC_API
                + "/magellan/v2/setups/"
                + str(self._setup["id"]),
                json=json_data,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status in (200, 204):
                    if timestampStart is not None and timestampEnd is not None:
                        valueTimestamps = (
                            "[" + str(timestampStart) + "," + str(timestampEnd) + "]"
                        )
                        await self.set_capability_value(
                            capabilityIdTimestamps, valueTimestamps
                        )
                        _LOGGER.info(
                            "Away mode enabled %d -> %d", timestampStart, timestampEnd
                        )
                    else:
                        valueTimestamps = "[0,0]"
                        await self.set_capability_value(
                            capabilityIdTimestamps, valueTimestamps
                        )
                        _LOGGER.info("Away mode disabled")

                    if capabilityIdMode is not None and valueMode is not None:
                        await self.set_capability_value(capabilityIdMode, valueMode)

                    self._timestamp_away_mode_last_change = None
                else:
                    _LOGGER.error(
                        "Set away mode : response %d (%s)",
                        response.status,
                        str(response.request_info),
                    )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
