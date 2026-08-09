from __future__ import annotations

import json
from pathlib import Path

from lantern.cli import run

from conftest import FIXTURE_PATH


def test_required_cli_commands_cover_seeded_workflow(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    assert run(["--project", str(project), "init", "--seed-fixture", str(FIXTURE_PATH)]) == 0
    init_output = json.loads(capsys.readouterr().out)
    assert init_output["status"] == "OK"
    assert run(["--project", str(project), "status"]) == 0
    status_output = json.loads(capsys.readouterr().out)
    assert len(status_output["result"]["review_required"]) == 2
    export_path = tmp_path / "export"
    assert run(["--project", str(project), "export", str(export_path)]) == 0
    capsys.readouterr()
    imported = tmp_path / "imported"
    assert run(["--project", str(imported), "import", str(export_path), "--create"]) == 0
    import_output = json.loads(capsys.readouterr().out)
    assert import_output["result"]["summary"]["CREATED"] > 0
