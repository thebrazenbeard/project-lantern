from __future__ import annotations

import json
from pathlib import Path

import pytest

from lantern.fixture import apply_fixture
from lantern.store import LanternStore

ARTIFACT_ROOT = Path(__file__).parents[2] / "projects" / "lantern" / "artifacts" / "benchmark"
FIXTURE_PATH = ARTIFACT_ROOT / "fixture-v1.json"
EXPECTED_PATH = ARTIFACT_ROOT / "expected-answers-v1.json"


@pytest.fixture
def fixture_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def expected_data() -> dict:
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def seeded_store(tmp_path: Path, fixture_data: dict):
    root = tmp_path / "seeded"
    store = LanternStore.initialize(root, project_id=fixture_data["project_id"], actor_id="operator-1")
    apply_fixture(store, FIXTURE_PATH)
    try:
        yield store
    finally:
        store.close()
