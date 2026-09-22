"""What the catalogue watcher does with an answer from Atlantic.

The watcher is a script, not part of the integration, and it runs unattended
twice a month against a live account. Both halves fail silently: a reshuffled
list would open an issue saying 405 capabilities changed, and a truncated
answer would rewrite the file with the rest deleted.
"""

import importlib.util
import pathlib

import pytest

SCRIPT = (
    pathlib.Path(__file__).resolve().parent.parent
    / "scripts"
    / "check_capability_catalogue.py"
)


@pytest.fixture
def watcher(tmp_path):
    """The script, with its catalogue file pointed at a temporary one."""
    spec = importlib.util.spec_from_file_location("catalogue_watch", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CATALOGUE = tmp_path / "capability_catalogue.jsonl"
    module.token = lambda: "token"
    return module


def items(count: int = 400, **edits) -> list[dict]:
    built = [
        {"id": i, "name": f"CAP_{i}", "type": 5, "unit": None, "enum": None}
        for i in range(1, count + 1)
    ]
    for index, value in edits.items():
        built[int(index)] = {**built[int(index)], **value}
    return built


def test_an_unchanged_catalogue_says_so(watcher):
    watcher.catalogue = lambda token: items()
    assert watcher.main() == 1  # first run, the file did not exist
    assert watcher.main() == 0


def test_the_api_reordering_its_answer_is_not_a_change(watcher):
    watcher.catalogue = lambda token: items()
    watcher.main()
    watcher.catalogue = lambda token: list(reversed(items()))
    assert watcher.main() == 0


def test_a_new_id_is_a_change(watcher):
    watcher.catalogue = lambda token: items()
    watcher.main()
    watcher.catalogue = lambda token: [
        *items(),
        {"id": 999999, "name": "BRAND_NEW", "type": 5, "unit": None, "enum": None},
    ]
    assert watcher.main() == 1


def test_a_renamed_id_is_a_change(watcher):
    watcher.catalogue = lambda token: items()
    watcher.main()
    watcher.catalogue = lambda token: items(**{"3": {"name": "RENAMED"}})
    assert watcher.main() == 1


def test_a_truncated_answer_is_refused_rather_than_written(watcher):
    watcher.catalogue = lambda token: items()
    watcher.main()
    before = watcher.CATALOGUE.read_text()
    watcher.catalogue = lambda token: items(count=10)
    assert watcher.main() == 2
    assert watcher.CATALOGUE.read_text() == before
