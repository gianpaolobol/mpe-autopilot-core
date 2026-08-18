import pytest

from autopilot_core.store import FileRuntimeStore


def test_runtime_store_rejects_path_traversal(tmp_path):
    store = FileRuntimeStore(tmp_path / "runtime")
    with pytest.raises(ValueError, match="escapes"):
        store.write_json({"unsafe": True}, "..", "outside.json")
