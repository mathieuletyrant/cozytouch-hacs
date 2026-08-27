"""Binary sensors for Atlantic Cozytouch integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .hub import CozytouchConfigEntry, Hub

_LOGGER = logging.getLogger(__name__)


# config flow setup
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CozytouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up entry."""
    # Retrieve the coordinator object
    coordinator = config_entry.runtime_data

    async_add_entities(
        [CloudConnectivity(coordinator, config_entry.title, config_entry.entry_id)],
        True,
    )


class CloudConnectivity(CoordinatorEntity, BinarySensorEntity):
    """Cloud connectivity to the Atlantic Cozytouch integration."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Cozytouch"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: Hub, title: str, uniq_id: str) -> None:
        """Initialize the Cloud connectivity binary sensor."""
        super().__init__(coordinator)
        self._title = title
        self._attr_unique_id = f"{DOMAIN}_{uniq_id}_cloud_connectivity"
        self._device_uniq_id = uniq_id if uniq_id is not None else "yaml_legacy"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        modelInfos = self.coordinator.get_model_infos()
        info = DeviceInfo(
            identifiers={(DOMAIN, self._device_uniq_id)},
            manufacturer="Atlantic",
            name=self._title,
            model=modelInfos.name,
            serial_number=self.coordinator.get_serial_number(),
            # The firmware the device reports (capability 121). It is worth
            # having on the device rather than only as a diagnostic entity:
            # "which version is this box on" is the first line of a bug
            # report, and None here just leaves the field empty.
            sw_version=self.coordinator.get_software_version(),
        )
        # Hang the device under its gateway when that is set up too, instead
        # of leaving every room unit at the top of the list. via_device is
        # deprecated for via_device_id, which needs a registry lookup and a
        # newer HA than this integration asks for.
        via_device = self.coordinator.get_via_device()
        if via_device is not None:
            info["via_device"] = via_device
        return info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.online
        self.async_write_ha_state()
