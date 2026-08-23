"""Put the repository root on the path so custom_components is importable.

The insert is also how Home Assistant itself finds the integration in the
tests under tests/integration: HA discovers custom components by importing
`custom_components` as a namespace package off sys.path and reading its
__path__, so the repository root being importable is what makes the
integration loadable at all.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pytest_ignore_collect(collection_path, config):
    """Collect tests/integration only under the configuration written for it.

    Those tests need pytest-asyncio in auto mode, which pytest-ha.ini sets and
    pyproject.toml -- plain `pytest`, the unit suite -- does not. Collected
    under the default strict mode each of them would fail on a `hass` fixture
    handed over as a coroutine, for a reason that reads like nothing to do with
    the cause. Ignoring the directory also covers the unit environment, where
    the plugin that provides that fixture is not installed at all.
    """
    if collection_path.name == "integration" and (
        config.inipath is None or config.inipath.name != "pytest-ha.ini"
    ):
        return True

    return None
