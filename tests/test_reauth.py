"""Telling a wrong password apart from a server that is not answering.

Both used to end the same way: `online = False`, then ConfigEntryNotReady, then
retry forever with the credentials that were already refused. Somebody who
changed their Cozytouch password saw an integration that could not connect and
was never asked for the new one.

These cover the whole path -- what the token endpoint said, what the hub raises,
what setup and the coordinator turn it into, and what the dialog does with the
password somebody types. `hub.py` had no tests at all before this file, so the
stand-ins here are the first of their kind in the suite: an aiohttp session
answering from a script, and the flow driven with asyncio.run(), which is how
tests/test_repairs.py already drives the repair flow.
"""

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.cozytouch import config_flow as cf
from custom_components.cozytouch.hub import CannotConnect, Hub, InvalidAuth
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

TOKEN_OK = {"token_type": "Bearer", "access_token": "a-token", "expires_in": 3600}
SETUP_VIEW = [{"id": 1, "name": "Home", "devices": [], "zones": []}]


class FakeResponse:
    """One answer: a status and either a JSON body or an exception."""

    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    async def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """An aiohttp session that answers from a script instead of a network.

    Requests are matched on the tail of the URL, so a test says what the token
    endpoint replies without restating the whole route.
    """

    def __init__(self, answers, raises=None):
        self._answers = answers
        self._raises = raises
        self.closed = False
        self.requests = []

    def _answer(self, url):
        self.requests.append(url)
        if self._raises is not None:
            raise self._raises
        for tail, answer in self._answers.items():
            if tail in url:
                return answer
        raise AssertionError(f"no scripted answer for {url}")

    def post(self, url, **kwargs):
        return self._answer(url)

    def get(self, url, **kwargs):
        return self._answer(url)

    async def close(self):
        self.closed = True


def make_hub(answers, raises=None, username="someone@example.test"):
    """A hub wired to a scripted session, without touching a coordinator."""
    hub = object.__new__(Hub)
    hub._session = FakeSession(answers, raises)
    hub._username = username
    hub._password = "hunter2"
    hub._deviceId = 1
    hub._setup = {}
    hub._zones = {}
    hub._devices = []
    hub._access_token = ""
    hub._token_expiry = 0
    hub._dump_json = False
    hub._zoneId = -1
    hub.online = False
    hub._hass = SimpleNamespace()
    return hub


# ------------------------------------------------- what the hub makes of it


def test_a_refused_password_is_not_a_connection_problem():
    """invalid_grant is OAuth2's way of saying the credentials are wrong, and
    it is the one answer that must not be retried.
    """
    hub = make_hub({"/users/token": FakeResponse({"error": "invalid_grant"})})

    with pytest.raises(InvalidAuth):
        asyncio.run(hub.connect())

    assert hub.online is False


def test_a_malformed_token_response_is_a_connection_problem():
    """A body with no token in it is the gateway misbehaving, not proof about
    the password. Saying "invalid auth" here sends somebody to reset a
    password that was fine.
    """
    hub = make_hub({"/users/token": FakeResponse({"unexpected": "shape"})})

    assert asyncio.run(hub.connect()) is False
    assert hub.online is False


def test_a_network_failure_stays_a_connection_problem():
    hub = make_hub({}, raises=TimeoutError())

    assert asyncio.run(hub.connect()) is False
    assert hub.online is False


def test_a_good_password_connects():
    hub = make_hub(
        {
            "/users/token": FakeResponse(TOKEN_OK),
            "setupviewv2": FakeResponse(SETUP_VIEW),
        }
    )

    assert asyncio.run(hub.connect()) is True
    assert hub.online is True


# --------------------------------------- what setup and the coordinator do


def test_setup_asks_for_a_new_password_rather_than_retrying_the_old_one():
    """ConfigEntryAuthFailed is what starts a reauth flow. Before this, the
    same failure raised ConfigEntryNotReady and the entry retried the refused
    password for as long as the installation ran.
    """
    hub = make_hub({"/users/token": FakeResponse({"error": "invalid_grant"})})

    with pytest.raises(ConfigEntryAuthFailed):
        asyncio.run(hub.async_connect_or_raise())


def test_setup_still_retries_when_the_servers_are_down():
    hub = make_hub({}, raises=TimeoutError())

    with pytest.raises(ConfigEntryNotReady):
        asyncio.run(hub.async_connect_or_raise())


def test_a_poll_that_finds_the_password_refused_raises_for_reauth():
    """The coordinator answers ConfigEntryAuthFailed by starting the reauth
    flow, and UpdateFailed by scheduling another go with the same password.
    This is the path a password changed while Home Assistant was running takes.
    """
    hub = make_hub({"/users/token": FakeResponse({"error": "invalid_grant"})})
    hub.online = False

    with pytest.raises(ConfigEntryAuthFailed):
        asyncio.run(hub._async_update_data())


def test_a_poll_that_cannot_reach_the_servers_only_fails_the_update():
    from homeassistant.helpers.update_coordinator import UpdateFailed

    hub = make_hub({}, raises=TimeoutError())
    hub.online = False

    with pytest.raises(UpdateFailed):
        asyncio.run(hub._async_update_data())


# --------------------------------------------------------- the config flow


class FakeEntry:
    def __init__(self, entry_id, username, password="old", deviceId=1):
        self.entry_id = entry_id
        self.data = {
            "username": username,
            "password": password,
            "deviceId": deviceId,
        }
        self.options = {}


class FakeEntries:
    """The bit of hass.config_entries these steps reach for."""

    def __init__(self, entries):
        self._entries = entries
        self.reloaded = []

    def async_entries(self, domain):
        return list(self._entries)

    def async_update_entry(self, entry, data):
        entry.data = dict(data)

    def async_schedule_reload(self, entry_id):
        self.reloaded.append(entry_id)


def make_flow(entry, others=(), connect=None):
    """A reauth flow pointed at one entry, with validate_input stubbed."""
    flow = cf.ConfigFlow()
    flow.hass = SimpleNamespace(config_entries=FakeEntries([entry, *others]))
    flow._get_reauth_entry = lambda: entry

    aborted = {}

    def async_update_reload_and_abort(target, data_updates):
        target.data = {**target.data, **data_updates}
        aborted["entry"] = target
        aborted["data_updates"] = data_updates
        return {"type": "abort", "reason": "reauth_successful"}

    flow.async_update_reload_and_abort = async_update_reload_and_abort
    flow.async_show_form = lambda **kwargs: {"type": "form", **kwargs}

    return flow, aborted


def run_reauth(monkeypatch, flow, password):
    """Submit the dialog with a password, with the network stubbed out."""

    async def validate_input(hass, data):
        if data["password"] == "correct":
            return SimpleNamespace(close=_noop_close)
        if data["password"] == "offline":
            raise CannotConnect
        raise InvalidAuth

    monkeypatch.setattr(cf, "validate_input", validate_input)

    return asyncio.run(flow.async_step_reauth_confirm({"password": password}))


async def _noop_close():
    return None


def test_the_dialog_opens_on_the_password_step(monkeypatch):
    entry = FakeEntry("one", "someone@example.test")
    flow, _ = make_flow(entry)

    result = asyncio.run(flow.async_step_reauth({}))

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"


def test_the_dialog_names_the_account_it_is_asking_about(monkeypatch):
    """Somebody with two Cozytouch accounts needs to know which one is being
    refused before typing a password at it.
    """
    entry = FakeEntry("one", "someone@example.test")
    flow, _ = make_flow(entry)

    result = asyncio.run(flow.async_step_reauth_confirm())

    assert result["description_placeholders"] == {"username": "someone@example.test"}


def test_a_correct_password_is_stored(monkeypatch):
    entry = FakeEntry("one", "someone@example.test")
    flow, aborted = make_flow(entry)

    result = run_reauth(monkeypatch, flow, "correct")

    assert result["reason"] == "reauth_successful"
    assert aborted["data_updates"] == {"password": "correct"}
    assert entry.data["password"] == "correct"


def test_a_wrong_password_is_not_stored_and_says_so(monkeypatch):
    entry = FakeEntry("one", "someone@example.test")
    flow, aborted = make_flow(entry)

    result = run_reauth(monkeypatch, flow, "still wrong")

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["password"] == "old"
    assert aborted == {}


def test_an_outage_during_reauth_does_not_blame_the_password(monkeypatch):
    """The whole point of the split: a server that is not answering must not
    tell somebody the password they just typed correctly is wrong.
    """
    entry = FakeEntry("one", "someone@example.test")
    flow, _ = make_flow(entry)

    result = run_reauth(monkeypatch, flow, "offline")

    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data["password"] == "old"


def test_every_entry_on_the_account_gets_the_new_password(monkeypatch):
    """One entry per device, so an account holds several -- a gateway plus a
    unit per zone -- each with its own copy. Fixing one and leaving the rest
    would raise a reauth prompt per device for the same password.
    """
    entry = FakeEntry("one", "someone@example.test", deviceId=1)
    sibling = FakeEntry("two", "someone@example.test", deviceId=2)
    flow, _ = make_flow(entry, others=[sibling])

    run_reauth(monkeypatch, flow, "correct")

    assert sibling.data["password"] == "correct"
    assert flow.hass.config_entries.reloaded == ["two"]


def test_another_account_is_left_alone(monkeypatch):
    """Two Cozytouch accounts in one Home Assistant is allowed, and the
    password from one is not the password for the other.
    """
    entry = FakeEntry("one", "someone@example.test")
    stranger = FakeEntry("two", "somebody-else@example.test")
    flow, _ = make_flow(entry, others=[stranger])

    run_reauth(monkeypatch, flow, "correct")

    assert stranger.data["password"] == "old"
    assert flow.hass.config_entries.reloaded == []


def test_the_username_is_not_up_for_editing(monkeypatch):
    """Changing it would point the entry at a different account, where its
    stored deviceId means nothing -- or, worse, something else.
    """
    entry = FakeEntry("one", "someone@example.test")
    flow, _ = make_flow(entry)

    result = asyncio.run(flow.async_step_reauth_confirm())

    assert list(result["data_schema"].schema) == ["password"]
