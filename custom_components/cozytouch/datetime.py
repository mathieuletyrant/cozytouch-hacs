"""Date/Time for Atlantic Cozytouch integration."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CozytouchCapabilityVariableType
from .hub import CozytouchConfigEntry, Hub
from .infos import CapabilityType
from .sensor import CozytouchSensor

_LOGGER = logging.getLogger(__name__)


# config flow setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    # Retrieve the hub object
    hub = config_entry.runtime_data

    # Init datetimes
    datetimes = []
    capabilities = hub.get_capabilities_for_device()
    for capability in capabilities:
        if capability["type"] == CapabilityType.AWAY_MODE_TIMESTAMPS:
            for index, timestamp in enumerate(capability["timestamps"]):
                datetimes.append(
                    CozytouchAwayModeDateTime(
                        capability=capability,
                        config_title=config_entry.title,
                        config_uniq_id=config_entry.entry_id,
                        attr_uniq_id=f"{config_entry.entry_id}_{index}",
                        coordinator=hub,
                        name=timestamp.name,
                        icon=timestamp.icon,
                        separator=",",
                        timestamp_index=index,
                    )
                )

    # Add the entities to HA
    if len(datetimes) > 0:
        async_add_entities(datetimes, True)


class CozytouchAwayModeDateTime(DateTimeEntity, CozytouchSensor):
    """Class for away mode datetime entity."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        name: str | None = None,
        icon: str | None = None,
        separator: str | None = None,
        timestamp_index: int | None = None,
        attr_uniq_id: str | None = None,
    ) -> None:
        """Initialize a datetime Sensor."""
        super().__init__(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=attr_uniq_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
            value_type=CozytouchCapabilityVariableType.STRING,
        )
        self._separator = separator
        self._timestamp_index = timestamp_index

    async def async_set_value(self, value: datetime) -> None:
        """Update the current value."""
        timestamp = value.timestamp()
        if timestamp is not None:
            if self._timestamp_index == 0:
                await self.coordinator.set_away_mode_start(
                    self._capability["capabilityId"], int(timestamp)
                )
            elif self._timestamp_index == 1:
                await self.coordinator.set_away_mode_end(
                    self._capability["capabilityId"], int(timestamp)
                )

    @property
    def native_value(self) -> datetime | None:
        """Retrieve value from hub."""
        value = None
        if self._timestamp_index == 0:
            value = self.coordinator.get_away_mode_start()
        elif self._timestamp_index == 1:
            value = self.coordinator.get_away_mode_end()

        if value is not None and value > 0:
            return datetime.fromtimestamp(value, tz=dt_util.DEFAULT_TIME_ZONE)

        return None
