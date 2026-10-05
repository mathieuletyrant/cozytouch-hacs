"""Post screenshots on a pull request, from a laptop or a cloud session.

GitHub has no public API for comment attachments, and a Claude Code on the
web session refuses the GraphQL call `gh pr comment --attach` makes, and
REST writes to the Git Data API. So the images are committed with git
plumbing and pushed under a ref that is neither a branch nor a tag --
`refs/uploads/pr-<n>` -- and the comment points at them by commit SHA.
Nothing shows in the branch list, the pull request's diff, the releases or
HACS.

    python3 <repo>/scripts/test_ha/attach.py <pr> BODY.md SHOT.png...
    python3 <repo>/scripts/test_ha/attach.py <pr> --delete

BODY.md references each shot by its file name, `![Before](./before.png)` ;
each reference is rewritten to the uploaded image and the comment posted.
Running it again for the same pull request replaces the ref, so the older
images stop being reachable. `--delete` removes the ref once the pull request
is merged, and GitHub drops the images at its next garbage collection.

The push goes to the `origin` of the checkout holding this script, from
wherever it is run. The comment goes
through `gh api` (REST) ; where that is refused too, the script prints the
body to post by other means.
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
REPO = "repos/mathieuletyrant/cozytouch-hacs"
ORIGIN = "origin"
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


def git(*args, stdin=None):
    """One git command in this checkout ; its stripped output."""
    result = subprocess.run(  # noqa: S603 -- fixed command, our arguments
        ["git", *args],  # noqa: S607
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"git {args[0]}: {result.stderr.strip()}")
    return result.stdout.strip()


def upload(pr, shots):
    """Push the shots to refs/uploads/pr-<n> ; the commit's SHA.

    Built with git plumbing and pushed, because a cloud session's proxy
    refuses REST writes to the Git Data API (403, 2026-10-05) but lets git push.
    """
    entries = "".join(
        f"100644 blob {git('hash-object', '-w', str(shot))}\t{shot.name}\n"
        for shot in shots
    )
    tree = git("mktree", stdin=entries)
    commit = git("commit-tree", tree, "-m", f"Screenshots for pull request #{pr}")
    git("push", "--force", "-q", ORIGIN, f"{commit}:refs/uploads/pr-{pr}")
    return commit


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[1] == "--delete":
        git("push", "-q", ORIGIN, f":refs/uploads/pr-{args[0]}")
        print(f"refs/uploads/pr-{args[0]} deleted")
        return
    if len(args) < 3:
        raise SystemExit(__doc__)

    pr, body_file, *names = args
    shots = [pathlib.Path(name).resolve() for name in names]
    body = pathlib.Path(body_file).read_text()
    commit = upload(pr, shots)
    for shot in shots:
        url = f"{WEB}/blob/{commit}/{shot.name}?raw=true"
        body = body.replace(f"./{shot.name}", url).replace(f"({shot.name})", f"({url})")
    try:
        print(api("POST", f"issues/{pr}/comments", {"body": body})["html_url"])
    except SystemExit as refused:
        # Post it some other way, the GitHub MCP tools in a cloud session.
        print(f"{refused}\nThe images are up ; post this body yourself:\n\n{body}")


if __name__ == "__main__":
    main()
