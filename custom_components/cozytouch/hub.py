"""Atlantic Cozytouch Hub."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .account import API_DECLARED_FIELDS, CozytouchAccount, CozytouchApiError
from .capability import get_capability_infos
from .const import DOMAIN
from .model import CozytouchDeviceType, get_model_infos

_LOGGER = logging.getLogger(__name__)

# How often the coordinator asks Atlantic for a device's capabilities.
POLL_INTERVAL = timedelta(seconds=60)


@dataclass
class CozytouchRuntimeData:
    """What a loaded config entry carries.

    One account -- one login, one setup view -- and one hub per device, keyed
    by the subentry that device was added as. The subentry id is also the
    identity every entity of that device is registered under, so this mapping
    is what turns "which entity" into "which device" everywhere else.
    """

    account: CozytouchAccount
    hubs: dict[str, Hub]


# A config entry that carries its account and hubs, so platforms can read them
# off the entry instead of looking them up in hass.data by id.
type CozytouchConfigEntry = ConfigEntry[CozytouchRuntimeData]


class Hub(DataUpdateCoordinator):
    """One device of an Atlantic Cozytouch account.

    The account -- the session, the token, the setup view, the list of devices
    -- lives in `account.py` and is shared. What is left here is per device:
    which capability ids this one reports, what its model makes of them, the
    60-second poll that refreshes them, and the away-mode window staged before
    it is committed.
    """

    manufacturer = "Atlantic Group"

    def __init__(
        self,
        hass: HomeAssistant,
        account: CozytouchAccount,
        deviceId: int | None = None,
        config_entry: ConfigEntry | None = None,
        subentry_id: str | None = None,
    ) -> None:
        """Init hub."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Cozytouch_" + str(deviceId),
            update_interval=POLL_INTERVAL,
        )
        self._account = account
        self._hass = hass
        self._entry = config_entry
        self._subentry_id = subentry_id
        self._deviceId = deviceId
        self._create_unknown = False

        # Staged rather than sent : editing the start or the end of the away
        # window stamps the change, and _async_update_data commits it once the
        # stamp is more than 20 seconds old, so both ends can be set first.
        self._timestamp_away_mode_last_change = None
        self._timestamp_away_mode_start = None
        self._timestamp_away_mode_end = None
        self._timestamps_away_mode_capability_id = None

    @property
    def account(self) -> CozytouchAccount:
        """The account this device hangs off."""
        return self._account

    @property
    def subentry_id(self) -> str | None:
        """The subentry this device was added as.

        It is the identity of the device everywhere it is visible : the device
        registry entry, and the unique id of every entity built from it.
        """
        return self._subentry_id

    @property
    def online(self) -> bool:
        """Whether the account this device belongs to is connected."""
        return self._account.online

    def set_create_entities_for_unknown_entities(self, create_unknown: bool) -> None:
        """Set option from config flow to create entities for unknown capabilities."""
        self._create_unknown = create_unknown

    def get_create_entities_for_unknown_entities(self) -> bool:
        """Get option from config flow to create entities for unknown capabilities."""
        return self._create_unknown

    async def _async_update_data(self):
        _LOGGER.debug("_async_update_data %d", self._deviceId)

        # Proactively re-authenticate if the token is about to expire
        self._account.check_token()

        if not self._account.online:
            # ConfigEntryAuthFailed passes straight through the coordinator,
            # which answers it by opening a reauth dialog and by not
            # rescheduling itself. UpdateFailed would only book another attempt
            # with the same rejected password.
            if not await self._account.connect_or_auth_failed():
                raise UpdateFailed("Cannot connect to Atlantic Cozytouch API")

            # A reconnect re-reads the setup view, which carries the capability
            # list of every device, so this round has nothing left to fetch.
            return

        try:
            capabilities = await self._account.fetch_capabilities(self._deviceId)
        except CozytouchApiError as err:
            raise UpdateFailed(str(err)) from err

        self._account.store_capabilities(self._deviceId, capabilities)

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

    def get_zone_name(self, zoneId: int | None = None) -> str:
        """Get zone infos."""
        return self._account.get_zone_name(zoneId)

    def get_unmapped_models(self) -> list[int]:
        """Every model id on the account the table has no branch for."""
        return self._account.get_unmapped_models()

    def get_model_infos(self, deviceId: int | None = None) -> str:
        """Get model infos."""
        if not deviceId:
            deviceId = self._deviceId

        for dev in self._account.devices:
            if dev["deviceId"] == deviceId:
                zoneId = dev["zoneId"]

                # Special case for sub-devices, use master zone Id
                for masterDev in self._account.devices:
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

    def get_model_id(self, deviceId: int | None = None) -> int | None:
        """The model id the API reports, which is what the mapping is keyed on.

        get_model_infos answers what the table made of it; this answers what
        the device said, which is what a bug report has to carry.
        """
        if not deviceId:
            deviceId = self._deviceId

        for dev in self._account.devices:
            if dev["deviceId"] == deviceId:
                return dev["modelId"]

        return None

    def get_serial_number(self, deviceId: int | None = None) -> str:
        """Get serial number."""
        if not deviceId:
            deviceId = self._deviceId

        for dev in self._account.devices:
            if dev["deviceId"] == deviceId:
                return dev["gatewaySerialNumber"]

        return "Unknown"

    def get_via_device(self, deviceId: int | None = None) -> tuple[str, str] | None:
        """Identifiers of the gateway this device hangs off, when HA has it.

        The API declares the topology itself: every room unit and thermal zone
        on the account carries the gateway's id in masterDeviceId. Home
        Assistant can only draw the link if the gateway was added too, since a
        device here is registered under the subentry it was added as -- so this
        returns None for a gateway, and for a child whose gateway nobody added.

        None rather than a guess matters: HA logs a warning when via_device
        names a device that is not in the registry.
        """
        if not deviceId:
            deviceId = self._deviceId

        masterDeviceId = None
        for dev in self._account.devices:
            if dev["deviceId"] == deviceId:
                masterDeviceId = dev.get("masterDeviceId")
                break

        if not masterDeviceId:
            return None

        for subentry_id, subentry in self._entry.subentries.items():
            if subentry.data.get("deviceId") == masterDeviceId:
                return (DOMAIN, subentry_id)

        return None

    def get_capabilities_for_device(self, deviceId: int | None = None):
        """Get capabilities for a device."""
        if not deviceId:
            deviceId = self._deviceId

        capabilities = []
        for dev in self._account.devices:
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

    def get_capability_names(
        self, deviceId: int | None = None
    ) -> tuple[dict[int, str], list[int]]:
        """Split what a device reports into what the mapping names and what it
        does not.

        The second half is what a bug report about an unmapped model is made
        of, and it is read both by the diagnostics dump and by the repair that
        asks for one -- so the rule for "named" lives here rather than in each.
        """
        if not deviceId:
            deviceId = self._deviceId

        for dev in self._account.devices:
            if dev["deviceId"] != deviceId:
                continue

            modelInfos = get_model_infos(dev["modelId"])
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

            return mapped, sorted(unmapped)

        return {}, []

    def get_diagnostics(self) -> dict:
        """Describe the account as the API reports it, for a diagnostics dump.

        Every device the setup returns is listed, whether or not somebody
        added it, because what a mapping needs first is the model ids a user
        actually owns -- and now with the capability ids to go with them, since
        the setup view carries a capability list for every device on the
        account and the account keeps all of them. For a device nobody added,
        that list is whatever the last setup view said rather than a fresh
        poll, which is still what a mapping is written from.

        `isConfiguredHere` says which devices have a subentry, and so which
        lists a 60-second poll keeps fresh. It is a property of the account and
        not of the hub that happened to be asked : any of them describes the
        whole thing, and one dump per account is the point.
        """
        configured = {
            subentry.data.get("deviceId")
            for subentry in self._entry.subentries.values()
        }

        devices = []
        for dev in self._account.devices:
            modelInfos = get_model_infos(dev["modelId"])
            mapped, unmapped = self.get_capability_names(dev["deviceId"])

            devices.append(
                {
                    "deviceId": dev["deviceId"],
                    "name": dev["name"],
                    "modelId": dev["modelId"],
                    "productId": dev["productId"],
                    "zoneId": dev["zoneId"],
                    "zoneName": self.get_zone_name(dev["zoneId"]),
                    "tags": dev["tags"],
                    "isConfiguredHere": dev["deviceId"] in configured,
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
                    "capabilities": {
                        "mapped": mapped,
                        "unmapped": unmapped,
                        "values": {
                            cap["capabilityId"]: cap["value"]
                            for cap in dev["capabilities"]
                        },
                    },
                }
            )

        return {
            "setup": dict(self._account.setup),
            "zones": list(self._account.zones),
            "devices": devices,
        }

    def get_capability_value(
        self, capabilityId: int, defaultIfNotExist: str | None = "0"
    ):
        """Get value for a device capability."""
        for dev in self._account.devices:
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
        if not self.online:
            return

        for dev in self._account.devices:
            if dev["deviceId"] != self._deviceId:
                continue

            for capability in dev["capabilities"]:
                if capabilityId != capability["capabilityId"]:
                    continue

                # Only on a completed execution : a write that never lands has
                # to leave the local value alone, and let the next poll say
                # what the device really did.
                if await self._account.write_capability(
                    self._deviceId, capabilityId, value
                ):
                    capability["value"] = value

                return

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
        if not self.online:
            return

        # The window lives on the setup, not on the device, so it goes first
        # and the capability write only mirrors what was accepted.
        if not await self._account.set_absence(timestampStart, timestampEnd):
            return

        if timestampStart is not None and timestampEnd is not None:
            valueTimestamps = "[" + str(timestampStart) + "," + str(timestampEnd) + "]"
            await self.set_capability_value(capabilityIdTimestamps, valueTimestamps)
            _LOGGER.info("Away mode enabled %d -> %d", timestampStart, timestampEnd)
        else:
            await self.set_capability_value(capabilityIdTimestamps, "[0,0]")
            _LOGGER.info("Away mode disabled")

        if capabilityIdMode is not None and valueMode is not None:
            await self.set_capability_value(capabilityIdMode, valueMode)

        self._timestamp_away_mode_last_change = None
