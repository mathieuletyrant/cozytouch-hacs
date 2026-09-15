"""Date/Time for Atlantic Cozytouch integration."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .capability_table import CAPABILITIES
from .const import CozytouchCapabilityVariableType
from .hub import CozytouchConfigEntry, Hub, add_capability_entities
from .infos import CapabilityType
from .sensor import CozytouchSensor

_LOGGER = logging.getLogger(__name__)

# What actually commits a window: the switch writes the setup's absence and
# only then mirrors it onto the timestamps. A device reporting the pair
# without one of these can be read, not set -- see docs/decisions.md.
_AWAY_MODE_SWITCH_IDS = frozenset(
    capabilityId
    for capabilityId, row in CAPABILITIES.items()
    if row.type is CapabilityType.AWAY_MODE_SWITCH
)


# config flow setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    add_capability_entities(
        config_entry,
        async_add_entities,
        {CapabilityType.AWAY_MODE_TIMESTAMPS: _away_mode_datetimes},
    )


def _away_mode_datetimes(
    coordinator: Hub, capability, config_title: str, config_uniq_id: str
) -> list[CozytouchAwayModeDateTime]:
    """The two ends of the away window, which are one capability."""
    if all(
        coordinator.get_capability_value(capabilityId, None) is None
        for capabilityId in _AWAY_MODE_SWITCH_IDS
    ):
        return []

    return [
        CozytouchAwayModeDateTime(
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            attr_uniq_id=f"{config_uniq_id}_{index}",
            coordinator=coordinator,
            translation_key=timestamp.name,
            icon=timestamp.icon,
            timestamp_index=index,
        )
        for index, timestamp in enumerate(capability.timestamps)
    ]


class CozytouchAwayModeDateTime(DateTimeEntity, CozytouchSensor):
    """Class for away mode datetime entity."""

    def __init__(
        self,
        capability,
        config_title: str,
        config_uniq_id: str,
        coordinator: Hub,
        translation_key: str | None = None,
        icon: str | None = None,
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
            translation_key=translation_key,
            icon=icon,
            value_type=CozytouchCapabilityVariableType.STRING,
        )
        self._timestamp_index = timestamp_index

    async def async_set_value(self, value: datetime) -> None:
        """Update the current value."""
        timestamp = value.timestamp()
        if timestamp is not None:
            if self._timestamp_index == 0:
                await self.coordinator.set_away_mode_start(
                    self._capability.capabilityId, int(timestamp)
                )
            elif self._timestamp_index == 1:
                await self.coordinator.set_away_mode_end(
                    self._capability.capabilityId, int(timestamp)
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
