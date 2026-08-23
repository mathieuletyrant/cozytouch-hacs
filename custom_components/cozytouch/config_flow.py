"""Config flow for Atlantic Cozytouch integration."""
from __future__ import annotations

import ast
from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN

# Both come from hub, which is where they are raised. This module used to
# declare its own CannotConnect and InvalidAuth next to those: the InvalidAuth
# was never raised or caught, and the duplicate CannotConnect meant two
# different classes under one name, either of which could shadow the other
# depending on import order.
from .hub import CannotConnect, Hub, InvalidAuth

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict) -> Hub:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.

    Returns a connected hub, which the caller owns and has to close. Raises
    InvalidAuth when the account refused the credentials and CannotConnect
    when it could not be asked -- the caller shows a different message for
    each, since "check your password" is unhelpful advice during an outage.
    """
    hub = Hub(hass, data["username"], data["password"])
    try:
        result = await hub.test_connection()
    except Exception:
        # the caller only closes the hub it gets back, so close it on the way out
        await hub.close()
        raise

    if not result:
        await hub.close()
        raise CannotConnect

    return hub


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atlantic Cozytouch."""

    VERSION = 1
    # Pick one of the available connection classes in homeassistant/config_entries.py
    # This tells HA if it should be asking for updates, or it'll be notified of updates
    # automatically. This example uses PUSH, as the dummy hub will notify HA of
    # changes.
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Return the options flow, without which HA shows no Configure button."""
        return OptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                hub = await validate_input(self.hass, user_input)
                devices = hub.devices()
                await hub.close()

                new_devices = []
                current_entries = self._async_current_entries()

                for device in devices:
                    existing_entry = next(
                        (
                            entry
                            for entry in current_entries
                            if entry.data.get("deviceId", "") == device["deviceId"]
                        ),
                        None,
                    )
                    if not existing_entry:
                        new_devices.append(device)

                if len(new_devices) == 0:
                    raise NoNewDevice

                return self.async_show_form(
                    step_id="select_device",
                    data_schema=vol.Schema(
                        {
                            vol.Required("device"): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    mode=selector.SelectSelectorMode.LIST,
                                    options=[
                                        selector.SelectOptionDict(
                                            label=device["name"],
                                            value=str(
                                                {
                                                    "deviceId": device["deviceId"],
                                                    "name": device["name"],
                                                    "username": user_input["username"],
                                                    "password": user_input["password"],
                                                }
                                            ),
                                        )
                                        for device in new_devices
                                    ],
                                )
                            ),
                            vol.Required("create_unknown", default=False): bool,
                            vol.Required("dump_json", default=False): bool,
                        }
                    ),
                    errors=errors,
                )

            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                # Used to say invalid_auth too, so a timeout told people their
                # password was wrong and sent them off to reset it.
                errors["base"] = "cannot_connect"
            except NoNewDevice:
                errors["base"] = "No new device found"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # If there is no user input or there were errors, show the form again,
        # including any errors that were found with the input.
        user_schema = vol.Schema(
            {vol.Required("username"): str, vol.Required("password"): str}
        )

        return self.async_show_form(
            step_id="user", data_schema=user_schema, errors=errors
        )

    async def async_step_select_device(self, device_input=None):
        """Handle the device selection step."""
        if device_input is not None and "device" in device_input:
            device_data = ast.literal_eval(device_input["device"])
            device_data["create_unknown"] = device_input["create_unknown"]
            device_data["dump_json"] = device_input["dump_json"]

            await self.async_set_unique_id(
                "cozytouch_" + str(device_data["deviceId"]), raise_on_progress=False
            )
            return self.async_create_entry(
                title=device_data["name"],
                data=device_data,
            )

        return self.async_abort()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start over from a password Atlantic no longer accepts.

        Home Assistant calls this when setup or a poll raises
        ConfigEntryAuthFailed. Before, that path did not exist: a changed
        Cozytouch password left every entry on the account retrying the old
        one for as long as the installation ran, saying only that it could not
        connect.
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password again, and check it before storing it."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            # The username is not asked for again. Changing it would point the
            # entry at a different account, where this entry's deviceId means
            # nothing or, worse, something else.
            try:
                hub = await validate_input(
                    self.hass,
                    {
                        "username": entry.data["username"],
                        "password": user_input["password"],
                    },
                )
                await hub.close()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # One entry per device, so an account usually holds several --
                # a gateway plus a unit per zone -- each with its own copy of
                # the credentials. Fixing only the entry whose dialog was
                # answered leaves the rest retrying the old password and
                # raising a reauth prompt each, so the password somebody just
                # typed once is written to all of them.
                for other in self.hass.config_entries.async_entries(DOMAIN):
                    if other.entry_id == entry.entry_id:
                        continue
                    if other.data.get("username") != entry.data["username"]:
                        continue

                    self.hass.config_entries.async_update_entry(
                        other,
                        data={**other.data, "password": user_input["password"]},
                    )
                    self.hass.config_entries.async_schedule_reload(other.entry_id)

                return self.async_update_reload_and_abort(
                    entry, data_updates={"password": user_input["password"]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("password"): str}),
            description_placeholders={"username": entry.data["username"]},
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles the options of a Cozytouch device."""

    def _current(self, key: str) -> bool:
        """Read an option, falling back to the value picked at setup time."""
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, False)
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "create_unknown", default=self._current("create_unknown")
                    ): bool,
                    vol.Required(
                        "dump_json", default=self._current("dump_json")
                    ): bool,
                }
            ),
        )


class NoNewDevice(exceptions.HomeAssistantError):
    """Error to indicate we didn't find new device."""
