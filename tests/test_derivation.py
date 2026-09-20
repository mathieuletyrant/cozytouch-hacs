"""What a device says about itself, when the table says nothing.

The table is keyed on `modelId`, which Atlantic's own app never reads : it
classifies on `productId`, the parent's `productId`, and `modelFamily`, all
three of which the setup view sends and `account.py` already stores. The
fall-through asks those instead of giving up, so hardware nobody has mapped
still arrives typed.

These pin the seam, not the ranges -- `test_model.py` owns what the table
answers, and the ranges themselves are copied from `ProductType.java` and
recorded in docs/decisions.md. What matters here is the order of authority :
the table first, the device second, and never the other way round.
"""

from custom_components.cozytouch.model import (
    CozytouchDeviceType,
    get_device_model_infos,
    get_model_infos,
)


def device(deviceId, modelId, productId, masterDeviceId=None, modelFamily=None):
    """A device as the setup view sends it, trimmed to what the model reads."""
    return {
        "deviceId": deviceId,
        "modelId": modelId,
        "productId": productId,
        "masterDeviceId": masterDeviceId,
        "modelFamily": modelFamily,
        "name": "",
    }


def test_the_table_wins_over_what_the_device_declares():
    """The table is the override layer, which is the whole safety of this.

    1656 is a mapped water heater. A `productId` claiming it is a room air
    conditioner has to change nothing, or every deliberate suppression the
    table carries could be undone by a number on the wire.
    """
    infos = get_model_infos(1656, productId=26, masterProductId=96)

    assert infos["type"] is CozytouchDeviceType.WATER_HEATER
    assert infos["name"] == "Aeromax 6"


def test_an_unmapped_model_is_typed_by_its_product_id():
    """A `productId` of 53 is TD1, a towel rack, on 360 unnamed ids."""
    infos = get_model_infos(2222, productId=53)

    assert infos["type"] is CozytouchDeviceType.TOWEL_RACK
    assert infos["HVACModes"] == {0: "off", 4: "heat"}


def test_a_room_is_typed_by_the_interface_it_hangs_off():
    """A room's own id is an index. Its parent says what is in the room."""
    behind_a_clim_hub = [
        device(1, 4242, productId=26, masterDeviceId=2),
        device(2, 1758, productId=96),
    ]
    behind_a_heat_pump = [
        device(1, 4242, productId=26, masterDeviceId=2),
        device(2, 1691, productId=54),
    ]

    assert (
        get_device_model_infos(behind_a_clim_hub, behind_a_clim_hub[0])["type"]
        is CozytouchDeviceType.AC
    )
    assert (
        get_device_model_infos(behind_a_heat_pump, behind_a_heat_pump[0])["type"]
        is CozytouchDeviceType.THERMOSTAT
    )


def test_a_room_with_no_parent_stays_unknown():
    """Without the parent the id says only that it is a room somewhere.

    Guessing here is what the old fall-through effectively did by handing every
    557-561 to the air conditioner branch, and a radiator read as a clim.
    """
    orphan = [device(1, 4242, productId=26, masterDeviceId=99)]

    assert (
        get_device_model_infos(orphan, orphan[0])["type"]
        is CozytouchDeviceType.UNKNOWN
    )


def test_model_family_answers_where_no_product_id_is_assigned():
    """Atlantic leaves productId 0 on 528 catalogue ids, products included."""
    infos = get_model_infos(4242, productId=0, modelFamily="Water_Heater")

    assert infos["type"] is CozytouchDeviceType.WATER_HEATER


def test_a_device_that_declares_nothing_reads_as_it_always_did():
    """The fall-through keeps its old answer, so nothing regresses."""
    infos = get_model_infos(424242)

    assert infos["type"] is CozytouchDeviceType.UNKNOWN
    assert infos["name"] == "Unknown product (424242)"
    assert infos["HVACModes"] == {0: "off", 4: "heat"}


def test_a_gateway_is_not_typed_by_the_installation_it_fronts():
    """Order of the two signals, and the case that makes it matter.

    The Navizone sends `modelFamily` `Air_Conditioning` -- the installation
    it drives -- while its own `productId` says it is a hub. Reading the
    family first would turn every gateway into a climate entity.
    """
    infos = get_model_infos(4242, productId=96, modelFamily="Air_Conditioning")

    assert infos["type"] is CozytouchDeviceType.HUB


def test_a_derived_gateway_gets_no_absence_setpoint():
    """The gateway reports the away mode; it cannot hold a temperature for it.

    A flag left off is taken as held, so this is silent when wrong: the entity
    appears, and writing to it goes nowhere.
    """
    infos = get_model_infos(4242, productId=96)

    assert infos["type"] is CozytouchDeviceType.HUB
    assert infos["awayModeTemperatureAvailable"] is False


def test_a_derived_room_inherits_its_gateway_flags():
    """A room behind a clim gateway has no absence setpoint either."""
    behind = [
        device(1, 4242, productId=26, masterDeviceId=2),
        device(2, 4243, productId=96),
    ]

    assert (
        get_device_model_infos(behind, behind[0])["awayModeTemperatureAvailable"]
        is False
    )
