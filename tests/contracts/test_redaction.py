from rekanvault.governance.logging import redact_sensitive_data


def test_redact_sensitive_data_keys():
    event = {
        "event": "user_login",
        "access_token": "ya29.abcdef12345",
        "refresh_token": "secret_refresh_token_99",
        "nested": {
            "password": "supersecretpassword",
            "safe_key": "safe_value",
        },
    }

    redacted = redact_sensitive_data(None, "info", event)
    assert redacted["access_token"] == "[REDACTED]"
    assert redacted["refresh_token"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["safe_key"] == "safe_value"


def test_redact_sensitive_pattern_in_string():
    event = {
        "event": "api_call",
        "header": "Bearer ya29.a0ARzA34_sample_token",
    }
    redacted = redact_sensitive_data(None, "info", event)
    assert "[REDACTED]" in redacted["header"]
