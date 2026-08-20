"""Probe the Cozytouch API and print the shape of what each route returns.

A discovery tool, not part of the integration. Read-only: it authenticates,
GETs, and prints keys rather than a full dump, so the output can be pasted
into an issue without leaking an address or a serial number.

What this has already established -- and what is still worth trying -- is
written down in docs/api-surface.md. Read that before adding routes here, so
the ~90 paths already ruled out are not probed again.

Run from the repository root:

    umask 077
    pbpaste > ~/.cozytouch-pass          # keeps the password out of the
    COZYTOUCH_USER=you@example.com \     # shell history
      COZYTOUCH_PASS_FILE=~/.cozytouch-pass \
      python3 scripts/probe_api.py [--new-routes]
    rm -f ~/.cozytouch-pass

Reads are cheap: the integration itself polls one of these routes every 60
seconds per device. A *refused login* is the one thing not to repeat -- it is
what could lock an account -- so a rejected token stops the script instead of
retrying.
"""

import importlib.util
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request


def _const():
    """Load the integration's const.py without importing Home Assistant.

    Going through the package would pull in `__init__.py` and with it all of
    HA, which this script has no reason to require. Loading the one module by
    path keeps the API host and client id in a single place instead of copying
    them here to drift.
    """
    path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "custom_components"
        / "cozytouch"
        / "const.py"
    )
    spec = importlib.util.spec_from_file_location("cozytouch_const", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CONST = _const()
API = _CONST.COZYTOUCH_ATLANTIC_API
CLIENT_ID = _CONST.COZYTOUCH_CLIENT_ID

# The device fields model.py hardcodes or derives today. Printed per device so
# a dump from another product family can be compared against the table in
# docs/api-surface.md, which so far only covers air conditioning.
DEVICE_FIELDS = (
    "name",
    "customName",
    "longName",
    "modelFamily",
    "productRange",
    "productId",
    "isAvailable",
    "masterDeviceId",
    "zoneId",
)

# Routes the integration already polls, so running without --new-routes adds
# nothing an account does not do to itself every minute.
ROUTES_KNOWN = ("/magellan/refs/countries",)

# Routes that exist but which the integration never calls. Add candidates
# here; a 404 means the gateway does not route the path at all.
ROUTES_NEW = (
    "/magellan/devices",
    "/magellan/setups",
    "/magellan/gateways",
    "/magellan/zones",
)


def password() -> str:
    """Password from COZYTOUCH_PASS_FILE, else COZYTOUCH_PASS."""
    path = os.environ.get("COZYTOUCH_PASS_FILE")
    if path:
        # A trailing newline from an editor or a shell redirect is not part of
        # the password.
        return pathlib.Path(path).expanduser().read_text().strip("\r\n")
    return os.environ.get("COZYTOUCH_PASS", "")


def token() -> str:
    """Authenticate, or exit saying why."""
    data = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "scope": "openid",
            "username": "GA-PRIVATEPERSON/" + os.environ["COZYTOUCH_USER"],
            "password": password(),
        }
    ).encode()
    req = urllib.request.Request(
        API + "/users/token",
        data=data,
        headers={
            "Authorization": f"Basic {CLIENT_ID}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode())["access_token"]
    except urllib.error.HTTPError as err:
        sys.exit(
            f"login refused ({err.code}): {err.read().decode()[:200]}\n"
            "Check the credentials before running this again; repeated failed "
            "logins are what could lock the account."
        )


def get(url: str, access_token: str):
    """GET a route, returning (status, parsed body or error text)."""
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as err:
        # A route the gateway accepts can still 404 with an HTML page at the
        # backend, which is how refs/countries turned out to be dead.
        return err.code, err.read().decode()[:200]
    except Exception as err:  # noqa: BLE001
        return None, repr(err)


def shape(value, depth: int = 0) -> str:
    """Describe a payload by its keys, keeping one sample item per list."""
    pad = "  " * depth
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(shape(item, depth + 1))
            else:
                lines.append(f"{pad}{key} = {json.dumps(item)[:80]}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{pad}[] (empty)"
        return f"{pad}[{len(value)} items], first:\n" + shape(value[0], depth + 1)
    return f"{pad}{json.dumps(value)[:80]}"


def main() -> None:
    """Probe the setup view, then each route in turn."""
    if not os.environ.get("COZYTOUCH_USER"):
        sys.exit("set COZYTOUCH_USER")
    if not password():
        sys.exit("password is empty -- check COZYTOUCH_PASS_FILE")

    access_token = token()
    print("authenticated\n")

    # The setup view is what the integration builds every device from, and it
    # embeds each device's capabilities, so it answers most questions alone.
    status, setup = get(API + "/magellan/cozytouch/setupviewv2", access_token)
    print(f"=== /magellan/cozytouch/setupviewv2 -> {status}")
    device_ids = []
    if isinstance(setup, list) and setup:
        for device in setup[0].get("devices", []):
            device_ids.append(device["deviceId"])
            print(f"  device {device['deviceId']} modelId={device.get('modelId')}")
            for field in DEVICE_FIELDS:
                print(f"    {field} = {json.dumps(device.get(field))}")
            capabilities = device.get("capabilities") or []
            if capabilities:
                print(f"    capability item keys: {sorted(capabilities[0].keys())}")
                print(f"    sample: {json.dumps(capabilities[0])[:200]}")
    else:
        print(f"  unexpected payload: {str(setup)[:200]}")
    print()

    routes = list(ROUTES_KNOWN)
    routes += [f"/magellan/capabilities/?deviceId={d}" for d in device_ids[:1]]
    if "--new-routes" in sys.argv:
        routes += list(ROUTES_NEW)

    for route in routes:
        status, body = get(API + route, access_token)
        print(f"=== {route} -> {status}")
        print(shape(body, 1) if isinstance(body, (dict, list)) else f"  {body}")
        print()


if __name__ == "__main__":
    main()
