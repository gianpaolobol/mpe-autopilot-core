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
