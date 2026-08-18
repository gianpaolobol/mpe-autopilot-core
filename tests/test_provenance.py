import pytest

from autopilot_core.provenance import ProvenanceError, controller_sha_from_env, normalize_controller_sha


def test_normalize_controller_sha_accepts_exact_sha_and_lowercases():
    value = "ABCDEF0123456789ABCDEF0123456789ABCDEF01"
    assert normalize_controller_sha(value) == value.lower()


def test_normalize_controller_sha_fails_closed_on_malformed_value():
    with pytest.raises(ProvenanceError):
        normalize_controller_sha("deadbeef")


def test_controller_sha_from_env_prefers_explicit_autopilot_provenance():
    env = {
        "AUTOPILOT_CONTROLLER_SHA": "a" * 40,
        "GITHUB_SHA": "b" * 40,
    }
    assert controller_sha_from_env(env) == "a" * 40
