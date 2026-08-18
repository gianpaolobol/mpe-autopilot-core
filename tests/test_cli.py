import json

from autopilot_core.cli import main


def test_probe_cli_runs_non_destructive_control_plane_cycle(tmp_path, capsys):
    code = main([
        "probe",
        "--root",
        str(tmp_path),
        "--runner-id",
        "ci-probe",
        "--controller-sha",
        "c" * 40,
    ])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code == 0
    assert result["status"] == "PASS"
    assert result["result"] == "PROBE_COMPLETED"
    assert result["controller_sha"] == "c" * 40


def test_probe_cli_fails_closed_when_provenance_is_missing(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("AUTOPILOT_CONTROLLER_SHA", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    code = main([
        "probe",
        "--root",
        str(tmp_path),
        "--runner-id",
        "ci-probe",
    ])
    captured = capsys.readouterr()
    result = json.loads(captured.err)
    assert code == 2
    assert result["status"] == "FAIL"
    assert "provenance is required" in result["reason"]
