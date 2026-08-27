"""Switches for Atlantic Cozytouch integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    # One device per subentry, and its entities are registered under it :
    # the subentry id is the identity that used to be the entry's own, back
    # when an entry meant a device.
    for subentry_id, subentry in config_entry.subentries.items():
        hub = config_entry.runtime_data.hubs[subentry_id]

        # Init selects
        selects = []
        capabilities = hub.get_capabilities_for_device()
        for capability in capabilities:
            if capability.type == CapabilityType.SELECT:
                selects.append(
                    CozytouchSelect(
                        coordinator=hub,
                        capability=capability,
                        config_title=subentry.title,
                        config_uniq_id=subentry_id,
                    )
                )

        # Add the entities to HA
        if len(selects) > 0:
            async_add_entities(selects, True, config_subentry_id=subentry_id)


class CozytouchSelect(SelectEntity, CozytouchSensor):
    """Class for select entity."""

    def __init__(
        self,
        coordinator: Hub,
        capability,
        config_title: str,
        config_uniq_id: str,
        name: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a Select entity."""
        super().__init__(
            coordinator=coordinator,
            capability=capability,
            config_title=config_title,
            config_uniq_id=config_uniq_id,
            name=name,
            icon=icon,
        )
        modelInfos = self.coordinator.get_model_infos()
        if "modelList" in capability and capability.modelList in modelInfos:
            self._list = modelInfos.get(capability.modelList, None)
        else:
            self._list = {-1: "Undefined"}

        self.options = list(self._list.values())
        self.current_option = self.options[0]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        for value in self._list:
            if self._list[value] == option:
                await self.coordinator.set_capability_value(
                    self._capability.capabilityId,
                    str(value),
                )
                await self.coordinator.async_request_refresh()
                break

    def get_value(self) -> str:
        """Retrieve value from hub."""
        try:
            value = int(
                self.coordinator.get_capability_value(self._capability.capabilityId)
            )
            if value in self._list:
                self.current_option = self._list[value]
        except ValueError:
            return
