"""Post screenshots on a pull request, from a laptop or a cloud session.

GitHub has no public API for comment attachments, and a Claude Code on the
web session refuses the GraphQL call `gh pr comment --attach` makes. So the
images go into the repository through the REST Git Data API, under a ref
that is neither a branch nor a tag -- `refs/uploads/pr-<n>` -- and the
comment points at them by commit SHA. Nothing shows in the branch list, the
pull request's diff, the releases or HACS.

    python3 scripts/test_ha/attach.py <pr> BODY.md SHOT.png [SHOT.png ...]
    python3 scripts/test_ha/attach.py <pr> --delete

BODY.md references each shot by its file name, `![Before](./before.png)` ;
each reference is rewritten to the uploaded image and the comment posted.
Running it again for the same pull request replaces the ref, so the older
images stop being reachable. `--delete` removes the ref once the pull request
is merged, and GitHub drops the images at its next garbage collection.

Every call goes through `gh api` (REST), which authenticates on a laptop
with the user's login and in a cloud session through the GitHub proxy.
"""

import base64
import json
import pathlib
import subprocess
import sys

REPO = "repos/mathieuletyrant/cozytouch-hacs"
WEB = "https://github.com/mathieuletyrant/cozytouch-hacs"


def api(method, path, payload=None):
    """One REST call, JSON in and out."""
    result = subprocess.run(  # noqa: S603 -- fixed command, our arguments
        ["gh", "api", "-X", method, f"{REPO}/{path}", "--input", "-"],  # noqa: S607
        input=json.dumps(payload or {}),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"{method} {path}: {result.stderr.strip() or result.stdout}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def upload(pr, shots):
    """Commit the shots under refs/uploads/pr-<n> ; the commit's SHA."""
    tree = [
        {
            "path": shot.name,
            "mode": "100644",
            "type": "blob",
            "sha": api(
                "POST",
                "git/blobs",
                {
                    "content": base64.b64encode(shot.read_bytes()).decode(),
                    "encoding": "base64",
                },
            )["sha"],
        }
        for shot in shots
    ]
    commit = api(
        "POST",
        "git/commits",
        {
            "message": f"Screenshots for pull request #{pr}",
            "tree": api("POST", "git/trees", {"tree": tree})["sha"],
            "parents": [],
        },
    )["sha"]

    ref = f"refs/uploads/pr-{pr}"
    try:
        api("PATCH", f"git/{ref}", {"sha": commit, "force": True})
    except SystemExit:
        api("POST", "git/refs", {"ref": ref, "sha": commit})
    return commit


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[1] == "--delete":
        api("DELETE", f"git/refs/uploads/pr-{args[0]}")
        print(f"refs/uploads/pr-{args[0]} deleted")
        return
    if len(args) < 3:
        raise SystemExit(__doc__)

    pr, body_file, *names = args
    shots = [pathlib.Path(name) for name in names]
    body = pathlib.Path(body_file).read_text()
    commit = upload(pr, shots)
    for shot in shots:
        url = f"{WEB}/blob/{commit}/{shot.name}?raw=true"
        body = body.replace(f"./{shot.name}", url).replace(f"({shot.name})", f"({url})")
    comment = api("POST", f"issues/{pr}/comments", {"body": body})
    print(comment["html_url"])


if __name__ == "__main__":
    main()
