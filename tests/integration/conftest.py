"""What the integration tests run against.

These are the only tests that build a real Home Assistant -- the `hass` fixture
from pytest-homeassistant-custom-component, which is HA core's own pytest
plugin -- and drive the integration through it, as the config flow and the
entry lifecycle rather than as functions. The rest of the suite calls into the
tables and the value builders directly against stand-ins, which is why none of
it reaches the flow, `async_setup_entry`, or the entity registry.

Only the HTTP boundary is faked, and it is faked by replacing
`hub.ClientSession` rather than with the plugin's `aioclient_mock` fixture:
the Hub constructs its own aiohttp session instead of asking
homeassistant.helpers.aiohttp_client for the shared one, and aioclient_mock
only intercepts the shared one. The stand-in records whether it was closed,
which is what the leak comments in __init__.py are about and what nothing
else here can see.
"""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cozytouch import hub
from custom_components.cozytouch.const import DOMAIN

USERNAME = "someone@example.com"
PASSWORD = "hunter2"  # noqa: S105 -- the account is a fake, this is its password

# The account: a gateway and one thermostat behind it, which is the shape the
# mapping was built from. Capabilities come back for the configured device
# only -- the setup view carries them per device, and the Hub keeps the ones
# whose deviceId matches the config entry (hub.py, update_devices_from_json_data).
GATEWAY_ID = 1200001
DEVICE_ID = 1200002
GATEWAY_MODEL = 1457  # Cozytouch Bridge
DEVICE_MODEL = 235  # Thermostat Navilink Connect
ZONE = {"id": 991904, "name": "Mezzanine"}

# 7 is the mode capability this model's HVACModesCapabilityId claims, so it is
# what makes a climate entity exist; 40 and 117 are the setpoint and the room
# temperature it reads. 104050 is a SELF_DESCRIBING capability -- named,
# surfaced as a raw string, off by default -- and 999999 is not in the table at
# all, so it is only an entity when the create_unknown option is on. Together
# they cover every branch of Hub.get_capabilities_for_device.
CAPABILITIES = [
    {"capabilityId": 7, "value": "4"},
    {"capabilityId": 40, "value": "20.5"},
    {"capabilityId": 117, "value": "19.5"},
    {"capabilityId": 104050, "value": "0"},
    {"capabilityId": 999999, "value": "0"},
]

TOKEN = {
    "token_type": "Bearer",
    "access_token": "an-access-token",
    "expires_in": 3600,
}


def setup_view(devices=None):
    """The setupviewv2 payload, carrying the fields the Hub reads off it."""
    return [
        {
            "id": 1532156,
            "name": "Maison",
            "address": {"city": "Nantes"},
            "zones": [ZONE],
            "devices": devices if devices is not None else default_devices(),
        }
    ]


def default_devices():
    """The two devices the account reports."""
    return [
        device(GATEWAY_ID, GATEWAY_MODEL, "Bridge", capabilities=[]),
        device(DEVICE_ID, DEVICE_MODEL, "Thermostat", capabilities=CAPABILITIES),
    ]


def device(deviceId, modelId, name, capabilities):
    """One entry of the setup view's device list."""
    return {
        "deviceId": deviceId,
        "name": name,
        "gatewaySerialNumber": "3022-6760-8541",
        "modelId": modelId,
        "productId": 65,
        "zoneId": ZONE["id"],
        "capabilities": capabilities,
        "tags": [],
        "longName": name,
        "modelFamily": "NAVILINK",
        "productRange": "---",
        "masterDeviceId": None if deviceId == GATEWAY_ID else GATEWAY_ID,
        "isAvailable": True,
    }


class FakeResponse:
    """One canned answer, shaped like the bits of an aiohttp response read."""

    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        """Return the payload, or raise it when a test asked for a failure."""
        if isinstance(self._payload, Exception):
            raise self._payload

        return self._payload


class FakeRequest:
    """The async context manager `async with session.get(...)` expects."""

    def __init__(self, session, method, url):
        self._session = session
        self._method = method
        self._url = url

    async def __aenter__(self):
        return self._session.handle(self._method, self._url)

    async def __aexit__(self, *exc_info):
        return False


class FakeSession:
    """A stand-in for the aiohttp session the Hub builds for itself."""

    def __init__(self, api):
        self._api = api
        self.closed = False
        self.requests = []

    def get(self, url, **kwargs):
        return FakeRequest(self, "GET", url)

    def post(self, url, **kwargs):
        return FakeRequest(self, "POST", url)

    def handle(self, method, url):
        """Record the call and hand back what the API is set to answer."""
        self.requests.append((method, url))
        return self._api.answer(url)

    async def close(self):
        """Note the close, which is the invariant several tests are about."""
        self.closed = True


class FakeApi:
    """The three Cozytouch endpoints the Hub talks to, and their answers.

    A test says what the API does by assigning to an attribute: `api.token =
    {"error": "invalid_grant"}` is a rejected password, `api.capabilities_status
    = 500` is the first poll failing.

    It also carries the account's ids and credentials, so a test reads them off
    the fixture instead of importing them out of a conftest -- which would need
    this directory to be a package to be legal.
    """

    username = USERNAME
    password = PASSWORD
    gateway_id = GATEWAY_ID
    device_id = DEVICE_ID
    device_model = DEVICE_MODEL

    def __init__(self):
        self.token = dict(TOKEN)
        self.setup = setup_view()
        self.capabilities = list(CAPABILITIES)
        self.capabilities_status = 200
        self.sessions = []

    @property
    def credentials(self):
        """What the first step of the config flow asks for."""
        return {"username": self.username, "password": self.password}

    def new_session(self):
        """Build a session and keep it, so a test can see it was closed."""
        session = FakeSession(self)
        self.sessions.append(session)
        return session

    @property
    def session(self):
        """The session in use, which is the last one built."""
        return self.sessions[-1]

    def answer(self, url):
        """Route on the path, since that is all the Hub varies."""
        if "/users/token" in url:
            return FakeResponse(200, self.token)

        if "/magellan/cozytouch/setupviewv2" in url:
            return FakeResponse(200, self.setup)

        if "/magellan/capabilities/" in url:
            return FakeResponse(self.capabilities_status, self.capabilities)

        raise AssertionError(f"the integration asked for an unexpected URL: {url}")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Home Assistant only loads a custom component when this is requested."""
    return


@pytest.fixture
def api(monkeypatch):
    """The Cozytouch API, faked at the session the Hub creates."""
    api = FakeApi()
    monkeypatch.setattr(hub, "ClientSession", lambda *args, **kwargs: api.new_session())
    return api


@pytest.fixture
def entry():
    """A config entry for the thermostat the fake account reports."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Thermostat",
        unique_id=f"cozytouch_{DEVICE_ID}",
        data={
            "username": USERNAME,
            "password": PASSWORD,
            "deviceId": DEVICE_ID,
            "name": "Thermostat",
            "create_unknown": False,
            "dump_json": False,
        },
    )
