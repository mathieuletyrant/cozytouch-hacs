"""Atlantic Cozytouch Hub."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .account import (
    API_DECLARED_FIELDS,
    CozytouchAccount,
    CozytouchApiError,
    CozytouchRateLimited,
)
from .capability import get_capability_infos
from .const import DOMAIN
from .derive import declared_vs_derived, derive_model_infos
from .infos import CapabilityCategory, CapabilityInfos, CapabilityType
from .model import CozytouchDeviceType, get_model_infos

_LOGGER = logging.getLogger(__name__)

# How often the account asks Atlantic for the setup view.
#
# 30 seconds where every version of this integration has said 60, and it costs
# *less* : the setup view carries every device, so this is two requests a
# minute whatever the account holds, where the per-device poll it replaces was
# one per device per minute -- five for the gateway-plus-four-units account in
# docs/api-surface.md. Anything from three devices up is now both cheaper and
# twice as fresh.
#
# 30 is also what the account's own `rateLimit` says, which is the one reading
# of that field nothing contradicts. That is a coincidence worth naming and
# not evidence: `rate_limit` is used as a ceiling below, never as the source
# of this number.
DEFAULT_POLL_INTERVAL = 30

# Below this, the requests stop buying anything : Atlantic's cloud learns from
# the hardware on its own schedule, and no amount of asking makes a radiator
# report sooner. Kept as a floor on the option rather than as advice in a
# docstring nobody reads while typing 5.
MIN_POLL_INTERVAL = 15
MAX_POLL_INTERVAL = 600

POLL_INTERVAL_OPTION = "poll_interval"


@dataclass
class CozytouchRuntimeData:
    """What a loaded config entry carries.

    One account -- one login, one setup view, one poll -- and one hub per
    device, keyed by the subentry that device was added as. The subentry id is
    also the identity every entity of that device is registered under, so this
    mapping is what turns "which entity" into "which device" everywhere else.
    """

    account: CozytouchAccount
    hubs: dict[str, Hub]
    coordinator: AccountCoordinator

# The capability carrying the firmware version, named `version` by
# capability.py. Read by id here because the device registry wants a string on
# the device, not an entity somewhere in the list.
SOFTWARE_VERSION_CAPABILITY_ID = 121


# A config entry that carries its account and hubs, so platforms can read them
# off the entry instead of looking them up in hass.data by id.
type CozytouchConfigEntry = ConfigEntry[CozytouchRuntimeData]


def poll_interval(entry: ConfigEntry, rate_limit: int | None) -> timedelta:
    """How often to poll, from the option and what the account will allow.

    The ceiling is `rateLimit` read as requests per minute. Nobody knows that
    is what it counts -- docs/api-surface.md says so plainly -- but of the
    readings that a working 60-second-per-device poll does not already
    disprove, it is the strictest, and a ceiling wants the strictest. On the
    one account ever captured it is 30, which permits everything down to the
    floor and so never bites; on an account that declares 1, it does.
    """
    seconds = entry.options.get(
        POLL_INTERVAL_OPTION,
        entry.data.get(POLL_INTERVAL_OPTION, DEFAULT_POLL_INTERVAL),
    )

    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        seconds = DEFAULT_POLL_INTERVAL

    seconds = max(MIN_POLL_INTERVAL, min(MAX_POLL_INTERVAL, seconds))

    if rate_limit and rate_limit > 0:
        # One request per interval is the whole steady-state cost, so the
        # budget is spent when the interval drops below 60 / rateLimit.
        allowed = 60 / rate_limit
        if seconds < allowed:
            _LOGGER.warning(
                "Poll interval of %ds exceeds the account's declared rateLimit"
                " of %s; using %ds",
                seconds,
                rate_limit,
                int(allowed) + 1,
            )
            seconds = int(allowed) + 1

    return timedelta(seconds=seconds)


class AccountCoordinator(DataUpdateCoordinator):
    """The one thing on a beat : re-read the setup view, tell every hub.

    This used to be a coordinator per device, each fetching
    `/magellan/capabilities/?deviceId=` for its own -- N requests a minute for
    N devices. But the setup view answers for the whole account in one request
    (`account.refresh_setup`), which is why that shape was worth changing : the
    same budget buys N times the frequency, and the cost stops growing with the
    number of devices somebody ticked at setup.

    The hubs stay coordinators, with no schedule of their own. They are pushed
    to from here, which keeps every entity a `CoordinatorEntity` of its own
    device -- one device failing still shows as that device failing -- and
    leaves `async_request_refresh()` after a write working as it did.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        account: CozytouchAccount,
        config_entry: ConfigEntry,
        hubs: dict[str, Hub],
    ) -> None:
        """Init the account coordinator.

        The hubs are a constructor argument rather than something attached
        afterwards : a coordinator that polls before it knows who to tell would
        spend a request and drop the answer, and there is no moment in setup
        where that state is useful.
        """
        super().__init__(
            hass,
            _LOGGER,
            # Not the username, which is the obvious id and an email address :
            # this name reaches every debug line the coordinator writes.
            config_entry=config_entry,
            name="Cozytouch_" + config_entry.entry_id,
            update_interval=poll_interval(config_entry, account.rate_limit),
        )
        self._account = account
        self._hubs = hubs

    async def _async_update_data(self) -> None:
        """Read the setup view once, and hand it to every device."""
        self._account.check_token()

        if not self._account.online:
            # ConfigEntryAuthFailed passes straight through the coordinator,
            # which answers it by opening a reauth dialog and by not
            # rescheduling itself. UpdateFailed would only book another attempt
            # with the same rejected password.
            if not await self._account.connect_or_auth_failed():
                self._publish_error(UpdateFailed("Cannot connect to Atlantic"))
                raise UpdateFailed("Cannot connect to Atlantic Cozytouch API")

            # connect() reads the setup view itself, so this round is done.
            await self._publish()
            return

        try:
            await self._account.refresh_setup()
        except CozytouchRateLimited as err:
            # Not an UpdateFailed : being asked to slow down is not the same as
            # having failed, and marking every entity unavailable because the
            # account is a few seconds ahead of its budget would be a worse lie
            # than a value that is one poll old. The values stand, and the next
            # tick will find the backoff still holding and skip in turn.
            _LOGGER.debug("Poll skipped, backing off : %s", err)
            return
        except CozytouchApiError as err:
            self._publish_error(UpdateFailed(str(err)))
            raise UpdateFailed(str(err)) from err

        await self._publish()

    async def _publish(self) -> None:
        """Tell every hub its device has a fresh capability list."""
        for hub in self._hubs.values():
            await hub.async_account_updated()

    def _publish_error(self, err: Exception) -> None:
        """Mark every device unavailable, since the account they share failed.

        The failure belongs to the account, so it reaches the entities through
        the hub each of them listens to rather than through a coordinator none
        of them has.
        """
        for hub in self._hubs.values():
            hub.async_set_update_error(err)

def as_epoch(value) -> int | None:
    """A modificationDate as an int, or None when it says nothing.

    Anything missing, unparsable or at or below zero comes back None rather
    than as a date in 1970. The field is undocumented -- there is no catalogue
    to check it against, docs/api-surface.md says so -- so what it holds on
    hardware nobody has captured is a guess, and a wrong timestamp on a
    dashboard is worse than an empty one. A string is tolerated because `value`
    arrives from this API as one, which makes a stringified date unsurprising.
    """
    try:
        epoch = int(float(value))
    except (TypeError, ValueError):
        return None

    return epoch if epoch > 0 else None


class Hub(DataUpdateCoordinator):
    """One device of an Atlantic Cozytouch account.

    The account -- the session, the token, the setup view, the list of devices,
    and now the poll -- lives in `account.py` and is shared. What is left here
    is per device: which capability ids this one reports, what its model makes
    of them, and the away-mode window staged before it is committed.

    Still a coordinator, and deliberately so : every entity is a
    `CoordinatorEntity` of the device it belongs to, so a device can be
    unavailable on its own. What it no longer has is a schedule.
    `update_interval=None` means it never fires by itself; it is pushed to by
    `AccountCoordinator`, and it fetches on its own only when something asks --
    `async_request_refresh()` after a write, which is what makes a setpoint
    appear without waiting for the account's next tick.
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
            update_interval=None,
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

    async def async_account_updated(self) -> None:
        """The account has a fresh setup view; publish it as this device's data.

        Called by `AccountCoordinator` rather than by a clock. The setup view
        it just read carries this device's capability list along with every
        other one, so there is nothing left to fetch -- the values are already
        on `account.devices` and what remains is to tell the entities.
        """
        await self._commit_staged_away_mode()
        self.async_set_updated_data(None)

    async def _async_update_data(self):
        """Fetch this one device, for a refresh that could not wait.

        No longer the beat -- `AccountCoordinator` is -- so this runs when
        `async_request_refresh()` asks, which is after a write. Re-reading the
        whole account to confirm one setpoint would be the wrong trade at this
        one moment, which is why the per-device route survives its demotion.
        """
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
            await self._commit_staged_away_mode()
            return

        try:
            capabilities = await self._account.fetch_capabilities(self._deviceId)
        except CozytouchRateLimited:
            # Keep the values and stay available : the account is throttled,
            # not broken, and the next account poll will bring this device
            # along with the others once the backoff lifts.
            return
        except CozytouchApiError as err:
            raise UpdateFailed(str(err)) from err

        self._account.store_capabilities(self._deviceId, capabilities)
        await self._commit_staged_away_mode()

    async def _commit_staged_away_mode(self) -> None:
        """Send the away window once both ends have stopped moving.

        Editing the start or the end stages the value and stamps it; this
        commits it when that stamp is more than 20 seconds old, so somebody can
        set both ends before either is sent. It used to hang off this hub's own
        60-second poll, which no longer exists -- so it runs on every path that
        now stands in for it, the account's tick and a post-write refresh
        alike. Hanging it off one of them would have made the delay depend on
        which, and hanging it off neither would have made a staged window sit
        there for good.
        """
        if (
            self._timestamp_away_mode_last_change is None
            or self._timestamps_away_mode_capability_id is None
            or self._timestamp_away_mode_start is None
            or self._timestamp_away_mode_end is None
        ):
            return

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

                return get_model_infos(
                    dev["modelId"], self.get_zone_name(zoneId), dev.get("name")
                )

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

    def get_software_version(self) -> str | None:
        """The firmware version the device reports about itself, if it does.

        Only for the device this entry drives: capabilities are kept for that
        one alone. Devices that do not report 121 -- the gateways among them --
        get None, which leaves the registry field empty rather than filling it
        with a guess.
        """
        return self.get_capability_value(SOFTWARE_VERSION_CAPABILITY_ID, None)

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
                modelInfos = get_model_infos(
                    dev["modelId"], deviceName=dev.get("name")
                )
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
                        capability_infos = CapabilityInfos(
                            capabilityId=capability["capabilityId"],
                            name="Capability_" + str(capability["capabilityId"]),
                            type=CapabilityType.STRING,
                            category=CapabilityCategory.DIAG,
                        )

                    if capability_infos is not None and len(capability_infos) > 0:
                        capability_infos.deviceId = deviceId

                        isDuplicate = False
                        if "capabilityDuplicate" in capability_infos:
                            for cap in capabilities:
                                if (
                                    cap["capabilityId"]
                                    == capability_infos.capabilityDuplicate
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

            modelInfos = get_model_infos(dev["modelId"], deviceName=dev.get("name"))
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
        actually owns -- and with the capability ids to go with them, since the
        setup view carries a capability list for every device on the account
        and the account keeps all of them.

        Those lists are all as fresh as each other now that the setup view is
        the poll : a device nobody added is refreshed on the same tick as one
        somebody did, where it used to hold whatever the last reconnect said.
        Unmapped hardware is exactly what a dump is read for, so it is the half
        that gained the most.

        `isConfiguredHere` therefore says which devices have entities, and no
        longer implies anything about freshness. It is a property of the
        account and not of the hub that happened to be asked : any of them
        describes the whole thing, and one dump per account is the point.
        """
        configured = {
            subentry.data.get("deviceId")
            for subentry in self._entry.subentries.values()
        }

        # What the derivation needs and a device's own report does not carry:
        # the family of its master (`modelFamily` is null on everything behind
        # a hub) and whether anything names it as master.
        familyById = {
            dev["deviceId"]: dev.get("modelFamily")
            for dev in self._account.devices
        }
        masterIds = {
            dev.get("masterDeviceId")
            for dev in self._account.devices
            if dev.get("masterDeviceId") is not None
        }

        devices = []
        for dev in self._account.devices:
            # Zones are not hardware anybody has to map, and a dump is read to
            # find hardware that is. Listing them put two capability ids that
            # resolve to nothing -- one of them declined on purpose -- in front
            # of whoever reads it, which reads exactly like work to do.
            if (
                get_model_infos(dev["modelId"], deviceName=dev.get("name")).type
                is CozytouchDeviceType.ZONE
            ):
                continue

            modelInfos = get_model_infos(dev["modelId"], deviceName=dev.get("name"))
            mapped, unmapped = self.get_capability_names(dev["deviceId"])

            # The declared table's shadow: what the capabilities alone would
            # say, and where that would wire different entities. Reported so
            # every dump measures the derivation against the table on hardware
            # nobody here owns; see derive.py for why nothing acts on it.
            derived = derive_model_infos(
                dev,
                masterFamily=familyById.get(dev.get("masterDeviceId")),
                isMaster=dev["deviceId"] in masterIds,
            )
            declaredVsDerived = declared_vs_derived(
                modelInfos,
                derived,
                {cap["capabilityId"] for cap in dev["capabilities"]},
            )

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
                        "name": modelInfos.name,
                        "type": str(modelInfos.type),
                        "isMapped": modelInfos.type
                        is not CozytouchDeviceType.UNKNOWN,
                        "infos": {
                            key: str(value)
                            for key, value in modelInfos.items()
                            if key not in ("name", "type")
                        },
                        "derived": derived,
                        "declaredVsDerived": declaredVsDerived,
                    },
                    "capabilities": {
                        "mapped": mapped,
                        "unmapped": unmapped,
                        "values": {
                            cap["capabilityId"]: cap["value"]
                            for cap in dev["capabilities"]
                        },
                        # The API's own third field, under the API's own name.
                        # The values say what a capability holds; these say
                        # when the device last changed it, which is what tells
                        # a value that is wrong from an id the hardware never
                        # feeds at all -- the question every
                        # unmapped-capability report runs into.
                        "modificationDates": {
                            cap["capabilityId"]: as_epoch(
                                cap.get("modificationDate")
                            )
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

    def get_capability_modification_date(self, capabilityId: int) -> int | None:
        """When the device last changed one capability, as the API says.

        `modificationDate` is the third field of every capability item and the
        one nothing has ever read -- docs/api-surface.md records it as
        available and unused. It is already here: the poll copies each item
        whole, so this costs no request.
        """
        for dev in self._account.devices:
            if dev["deviceId"] == self._deviceId:
                for capability in dev["capabilities"]:
                    if capabilityId == capability["capabilityId"]:
                        return as_epoch(capability.get("modificationDate"))

        return None

    def get_last_modification_date(self) -> int | None:
        """The newest modification date this device reports, if it reports one.

        The whole device rather than one capability, because the question this
        answers is whether the hardware is still talking to Atlantic's cloud --
        and one capability can legitimately sit unchanged for hours, so the
        newest of all of them is the only honest reading of "still reporting".

        None means nothing on the device carries a usable date, which is why
        the sensor built from this is not created at all in that case rather
        than sitting there empty.
        """
        dates = [
            as_epoch(capability.get("modificationDate"))
            for dev in self._account.devices
            if dev["deviceId"] == self._deviceId
            for capability in dev["capabilities"]
        ]

        return max([date for date in dates if date is not None], default=None)

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


def device_info_for(coordinator: Hub, device_uniq_id: str) -> DeviceInfo:
    """The device every entity of one subentry belongs to.

    One function rather than a copy per entity class, and here rather than on
    the sensor platform: setup registers every device from this before any
    platform runs (see docs/decisions.md), so what the registry holds and what
    the entities later declare are the same description.
    """
    model_name = coordinator.get_model_infos().name
    info = DeviceInfo(
        identifiers={(DOMAIN, device_uniq_id)},
        manufacturer="Atlantic",
        name=model_name,
        model=model_name,
        serial_number=coordinator.get_serial_number(),
        # The firmware the device reports (capability 121). It is worth
        # having on the device rather than only as a diagnostic entity:
        # "which version is this box on" is the first line of a bug
        # report, and None here just leaves the field empty.
        sw_version=coordinator.get_software_version(),
    )
    # Hang the device under its gateway when that is set up too, instead
    # of leaving every room unit at the top of the list. via_device is
    # deprecated for via_device_id, which needs a registry lookup and a
    # newer HA than this integration asks for.
    via_device = coordinator.get_via_device()
    if via_device is not None:
        info["via_device"] = via_device

    return info
