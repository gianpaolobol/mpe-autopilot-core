from autopilot_core.sanitize import sanitize


def test_sanitize_redacts_sensitive_keys_and_token_shaped_strings():
    source = {
        "api_key": "top-secret",
        "nested": {
            "message": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
            "token": "github_pat_abcdefghijklmnopqrstuvwxyz123456",
        },
        "safe": "keep-me",
    }
    clean = sanitize(source)
    assert clean["api_key"] == "***"
    assert clean["nested"]["token"] == "***"
    assert "abcdefghijklmnopqrstuvwxyz" not in clean["nested"]["message"]
    assert clean["safe"] == "keep-me"
