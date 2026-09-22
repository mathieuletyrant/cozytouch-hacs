r"""Re-read Atlantic's capability catalogue and say what moved since last time.

`GET /magellan/productmodels/capabilities` is the vendor's own list : every
capability id with its name, description, type, unit, bounds, enum members and
an accessType bitmask. `capability_table.py` was built from a run of it, and
nothing tells us when Atlantic edits it -- a new id, a renamed one, an enum
that gained a value. A device reporting an unmapped id eventually says so
through the diagnostics dump, but only once somebody owns that hardware.

So the answer is kept in the repository, one capability per line, and this
re-fetches it and leaves the file rewritten. `git diff` is the report. Run
from the repository root :

    umask 077
    pbpaste > ~/.cozytouch-pass
    COZYTOUCH_USER=you@example.com \
      COZYTOUCH_PASS_FILE=~/.cozytouch-pass \
      python3 scripts/check_capability_catalogue.py
    rm -f ~/.cozytouch-pass

Exit code 0 when nothing moved, 1 when the file changed, 2 when the fetch
itself failed -- which is what `.github/workflows/catalogue.yaml` branches on.

One login, no retry. A refused login is reported and the run stops : repeated
failed logins are what could lock the account, and a fortnightly job that
retries is exactly how that would happen unattended.
"""

import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from custom_components.cozytouch.const import (
    COZYTOUCH_ATLANTIC_API,
    COZYTOUCH_CLIENT_ID,
)

CATALOGUE = pathlib.Path(__file__).resolve().parent / "capability_catalogue.jsonl"


def password() -> str:
    """The password, from a file rather than the environment or a prompt."""
    path = os.environ.get("COZYTOUCH_PASS_FILE")
    if path:
        return pathlib.Path(path).expanduser().read_text().strip()
    if "COZYTOUCH_PASS" in os.environ:
        return os.environ["COZYTOUCH_PASS"]
    sys.exit("Set COZYTOUCH_PASS_FILE (preferred) or COZYTOUCH_PASS.")


def token() -> str:
    data = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "scope": "openid",
            "username": "GA-PRIVATEPERSON/" + os.environ["COZYTOUCH_USER"],
            "password": password(),
        }
    ).encode()
    req = urllib.request.Request(
        COZYTOUCH_ATLANTIC_API + "/users/token",
        data=data,
        headers={
            "Authorization": f"Basic {COZYTOUCH_CLIENT_ID}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())["access_token"]


def catalogue(access_token: str) -> list[dict]:
    req = urllib.request.Request(
        COZYTOUCH_ATLANTIC_API + "/magellan/productmodels/capabilities",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode())


def rendered(items: list[dict]) -> str:
    """One capability per line, sorted, so a diff points at what changed.

    Sorted by id and with sorted keys, because the API's own ordering is not
    promised and a reshuffle would read as 405 changes.
    """
    lines = [
        json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for item in sorted(items, key=lambda item: item["id"])
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        items = catalogue(token())
    except urllib.error.HTTPError as err:
        print(f"{err.code} from Atlantic: {err.read().decode()[:200]}", file=sys.stderr)
        return 2
    except OSError as err:
        print(f"could not reach Atlantic: {err}", file=sys.stderr)
        return 2

    # A truncated answer would otherwise land as "Atlantic deleted 300
    # capabilities", which is the one diff nobody should ever be shown.
    if len(items) < 300:
        print(
            f"only {len(items)} capabilities came back; refusing to write.",
            file=sys.stderr,
        )
        return 2

    new = rendered(items)
    old = CATALOGUE.read_text() if CATALOGUE.exists() else ""
    if new == old:
        print(f"{len(items)} capabilities, unchanged.")
        return 0

    CATALOGUE.write_text(new)
    print(f"{len(items)} capabilities, and the catalogue changed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
