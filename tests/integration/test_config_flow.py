"""The config flow, walked the way the user walks it.

Nothing else in the suite touches it, and it is where the account is turned
into config entries: credentials, then one entry per device the account
reports and does not already have. Two of its habits are pinned here rather
than corrected, because they are what the released integration does and
changing either is a migration : the credentials make a round trip through the
form as a stringified dict, and the "no new device" case shows an English
sentence where every other error shows a translation key.
"""

import ast

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cozytouch.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType


async def start(hass):
    """Open the flow, as the Add Integration button does."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


def device_options(result):
    """The options of the select step, as the selector holds them."""
    schema = result["data_schema"].schema
    select = next(value for key, value in schema.items() if str(key) == "device")
    return select.config["options"]


def offered(result):
    """The devices the step is showing, label and decoded value."""
    return [
        (option["label"], ast.literal_eval(option["value"]))
        for option in device_options(result)
    ]


def value_for(result, label):
    """The opaque value the step wants back for one of the devices."""
    return next(
        option["value"]
        for option in device_options(result)
        if option["label"] == label
    )


async def test_the_flow_opens_on_the_credentials_form(hass, api):
    result = await start(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert {str(key) for key in result["data_schema"].schema} == {
        "username",
        "password",
    }


async def test_the_devices_the_account_reports_are_offered(hass, api):
    """Both, gateway included: the flow does not decide what is a product.

    tests/test_repairs.py pins the same choice on the repair side -- working
    out which devices are not really products was taken out rather than put in,
    because nothing in the payload says.
    """
    result = await hass.config_entries.flow.async_configure(
        (await start(hass))["flow_id"], api.credentials
    )

    assert result["step_id"] == "select_device"
    assert [label for label, _ in offered(result)] == ["Bridge", "Thermostat"]


async def test_the_credentials_travel_through_the_form_in_the_option_value(hass, api):
    """Pinned as it stands. The password goes out to the browser and back.

    Each option's value is `str(dict)` -- built in async_step_user and read
    back with ast.literal_eval in async_step_select_device -- so the account
    password is part of the form the user is shown. It is the only place the
    step keeps state, and the entry it writes needs it.
    """
    result = await hass.config_entries.flow.async_configure(
        (await start(hass))["flow_id"], api.credentials
    )

    _, thermostat = offered(result)[1]

    assert thermostat == {
        "deviceId": api.device_id,
        "name": "Thermostat",
        "username": api.username,
        "password": api.password,
    }


async def test_picking_a_device_creates_its_entry(hass, api):
    result = await hass.config_entries.flow.async_configure(
        (await start(hass))["flow_id"], api.credentials
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": value_for(result, "Thermostat"),
            "create_unknown": False,
            "dump_json": True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Thermostat"
    assert result["data"] == {
        "deviceId": api.device_id,
        "name": "Thermostat",
        "username": api.username,
        "password": api.password,
        "create_unknown": False,
        "dump_json": True,
    }

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == f"cozytouch_{api.device_id}"


@pytest.mark.parametrize(
    ("failure", "payload"),
    [
        ("token", {"error": "invalid_grant"}),
        ("setup", {"message": "Internal server error"}),
    ],
)
async def test_a_connection_that_does_not_work_is_reported_on_the_form(
    hass, api, failure, payload
):
    """Both come back as invalid_auth, which is only right for one of them.

    Hub.connect answers False for a rejected password and for a setup view it
    cannot read, and validate_input turns either into CannotConnect. The flow
    then shows `invalid_auth`, so an Atlantic outage tells the user their
    password is wrong.
    """
    setattr(api, failure, payload)

    result = await hass.config_entries.flow.async_configure(
        (await start(hass))["flow_id"], api.credentials
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_a_device_that_already_has_an_entry_is_not_offered_again(hass, api):
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"cozytouch_{api.device_id}",
        data={"deviceId": api.device_id, "name": "Thermostat"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        (await start(hass))["flow_id"], api.credentials
    )

    assert [label for label, _ in offered(result)] == ["Bridge"]


async def test_nothing_left_to_add_is_reported_as_an_untranslated_sentence(hass, api):
    """Pinned as it stands: the error is the message, not a key.

    Every other branch of the step sets a key that strings.json translates.
    This one sets the sentence itself, so the dialog shows the key as-is in
    every language.
    """
    for deviceId in (api.gateway_id, api.device_id):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id=f"cozytouch_{deviceId}",
            data={"deviceId": deviceId, "name": str(deviceId)},
        ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        (await start(hass))["flow_id"], api.credentials
    )

    assert result["errors"] == {"base": "No new device found"}


async def test_the_options_flow_offers_what_setup_chose(hass, api, entry):
    """The options flow is what the Configure button opens on an entry."""
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "dump_json": True}
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["step_id"] == "init"
    assert {
        str(key): key.default() for key in result["data_schema"].schema
    } == {"create_unknown": False, "dump_json": True}


async def test_the_options_flow_writes_the_options_and_reloads(hass, api, entry):
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"create_unknown": True, "dump_json": False}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"create_unknown": True, "dump_json": False}
    # the reload the update listener asks for, which is how the new option
    # reaches the entities that already exist
    assert len(api.sessions) == 2
