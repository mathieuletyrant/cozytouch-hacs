"""A throwaway Home Assistant running this integration against a fake cloud.

`fake_atlantic.py` serves a diagnostics dump as if it were the account ; this
starts it, starts Home Assistant with the integration copied from the working
tree -- its API address pointed at the fake -- onboards an owner and adds the
account, so the result is a running instance with every device of the dump
on it. Nobody's credentials are involved.

    python scripts/test_ha.py start DUMP.json   # fresh instance
    python scripts/test_ha.py restart           # recopy the code, full restart
    python scripts/test_ha.py stop
    python scripts/test_ha.py token             # a fresh access token

Home Assistant runs from the interpreter in HA_PYTHON (default: the one
running this), which needs `homeassistant` installed ; the frontend and the
default integrations' requirements are installed by Home Assistant itself on
first start. State lives in TEST_HA_DIR (default: ./.test-ha), which is
throwaway : `start` wipes it.
"""

import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = pathlib.Path(os.environ.get("TEST_HA_DIR", ROOT / ".test-ha")).resolve()
CONFIG = WORK / "config"
PYTHON = os.environ.get("HA_PYTHON", sys.executable)

HA_URL = "http://127.0.0.1:8123"
FAKE_PORT = 8765
CLIENT_ID = HA_URL + "/"

REAL_API = "https://apis.groupe-atlantic.com"

OWNER = {"name": "Test", "username": "test", "password": "test-password"}

CONFIGURATION = """\
homeassistant:
  time_zone: Europe/Paris
  country: FR
  language: fr
  unit_system: metric

default_config:

logger:
  default: warning
  logs:
    custom_components.cozytouch: debug
"""


def request(method, path, body=None, form=None, token=None, base=HA_URL):
    """One HTTP call, JSON in and out, raising on anything but 2xx."""
    data, headers = None, {}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read()
    except urllib.error.HTTPError as err:
        raise SystemExit(
            f"{method} {path} answered {err.code}: {err.read().decode()[:500]}"
        ) from err
    return json.loads(raw) if raw else None


def wait_for(url, seconds):
    """Until the URL answers at all, or give up."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=10)
            return
        except urllib.error.HTTPError as err:
            if err.code != 404:
                return
            time.sleep(2)
        except OSError:
            time.sleep(2)
    raise SystemExit(f"{url} did not come up within {seconds}s ; see {WORK}/*.log")


def spawn(name, argv):
    """Start a process detached from this one, its output in WORK/<name>.log."""
    log = open(WORK / f"{name}.log", "ab")  # noqa: SIM115 -- the child keeps it
    # Not from the repository : `python -m` puts the working directory on the
    # path, and its `custom_components` would shadow the patched copy.
    # S603: argv is built here from this interpreter and this repository.
    process = subprocess.Popen(  # noqa: S603
        argv,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=WORK,
    )
    (WORK / f"{name}.pid").write_text(str(process.pid))


def kill(name):
    pidfile = WORK / f"{name}.pid"
    if not pidfile.exists():
        return
    pid = int(pidfile.read_text())
    try:
        os.killpg(pid, signal.SIGTERM)
        for _ in range(30):
            os.kill(pid, 0)
            time.sleep(1)
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    pidfile.unlink()


def copy_integration():
    """The working tree's integration, talking to the fake instead of Atlantic."""
    target = CONFIG / "custom_components" / "cozytouch"
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(
        ROOT / "custom_components" / "cozytouch",
        target,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    const = target / "const.py"
    text = const.read_text()
    if REAL_API not in text:
        raise SystemExit("const.py no longer names the API address this replaces")
    const.write_text(text.replace(REAL_API, f"http://127.0.0.1:{FAKE_PORT}"))


def start_ha():
    spawn("hass", [PYTHON, "-m", "homeassistant", "-c", str(CONFIG)])
    # The API answers before startup is over ; onboarding only once the
    # default integrations are set up, which on a first start includes
    # installing their requirements.
    wait_for(HA_URL + "/api/", 900)
    wait_for(HA_URL + "/api/onboarding", 900)


def onboard():
    """Create the owner and finish onboarding ; keep a refresh token."""
    code = request(
        "POST",
        "/api/onboarding/users",
        {**OWNER, "client_id": CLIENT_ID, "language": "fr"},
    )["auth_code"]
    tokens = request(
        "POST",
        "/auth/token",
        form={"grant_type": "authorization_code", "code": code, "client_id": CLIENT_ID},
    )
    (WORK / "tokens.json").write_text(json.dumps(tokens))

    access = tokens["access_token"]
    request("POST", "/api/onboarding/core_config", {}, token=access)
    request("POST", "/api/onboarding/analytics", {}, token=access)
    request(
        "POST",
        "/api/onboarding/integration",
        {"client_id": CLIENT_ID, "redirect_uri": CLIENT_ID},
        token=access,
    )


def access_token():
    tokens = json.loads((WORK / "tokens.json").read_text())
    return request(
        "POST",
        "/auth/token",
        form={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": CLIENT_ID,
        },
    )["access_token"]


def add_account():
    """The config flow, as the UI would run it : account, then every device."""
    token = access_token()
    flow = request(
        "POST", "/api/config/config_entries/flow", {"handler": "cozytouch"}, token=token
    )
    step = request(
        "POST",
        f"/api/config/config_entries/flow/{flow['flow_id']}",
        {"username": "fake@example.com", "password": "fake"},
        token=token,
    )
    if step.get("type") == "form":
        step = request(
            "POST",
            f"/api/config/config_entries/flow/{flow['flow_id']}",
            {"create_unknown": False, "dump_json": False},
            token=token,
        )
    if step.get("type") != "create_entry":
        raise SystemExit(f"The config flow stopped at {step}")


def start(dump):
    kill("hass")
    kill("fake")
    shutil.rmtree(WORK, ignore_errors=True)
    CONFIG.mkdir(parents=True)
    (CONFIG / "configuration.yaml").write_text(CONFIGURATION)

    spawn(
        "fake",
        [
            PYTHON,
            str(ROOT / "scripts" / "fake_atlantic.py"),
            str(pathlib.Path(dump).resolve()),
            "--port",
            str(FAKE_PORT),
        ],
    )
    wait_for(f"http://127.0.0.1:{FAKE_PORT}/fake/journal", 30)

    copy_integration()
    start_ha()
    onboard()
    add_account()
    print(f"Home Assistant is up on {HA_URL}, owner {OWNER['username']}")


def restart():
    kill("hass")
    copy_integration()
    start_ha()
    print(f"Restarted on {HA_URL}")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    command = sys.argv[1]
    if command == "start" and len(sys.argv) == 3:
        start(sys.argv[2])
    elif command == "restart":
        restart()
    elif command == "stop":
        kill("hass")
        kill("fake")
    elif command == "token":
        print(access_token())
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
