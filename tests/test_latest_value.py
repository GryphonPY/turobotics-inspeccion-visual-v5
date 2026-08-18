from __future__ import annotations

from inspection_v5.latest_value import LatestValue


def test_latest_value_returns_only_newest_item() -> None:
    store = LatestValue[str]()
    store.publish("old")
    version = store.publish("new")

    assert store.read()[1] == "new"
    assert store.read(after_version=version) == (version, None)


def test_clear_removes_value_and_advances_version() -> None:
    store = LatestValue[str]()
    first = store.publish("value")

    store.clear()

    version, value = store.read()
    assert version == first + 1
    assert value is None
