import pytest

from briefing_skill.emailer import resolve_smtp_config


BASE = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_USERNAME": "username@example.com",
    "EMAIL_TO": "one@example.com, two@example.com",
}


def test_smtp_sender_and_recipient_alias_precedence():
    config = resolve_smtp_config(
        {
            **BASE,
            "EMAIL_FROM": "email-from@example.com",
            "SMTP_FROM": "smtp-from@example.com",
            "SMTP_TO": "ignored@example.com",
        }
    )
    assert config.sender == "email-from@example.com"
    assert config.recipients == ("one@example.com", "two@example.com")

    aliases = resolve_smtp_config(
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_USERNAME": "username@example.com",
            "EMAIL_FROM": "   ",
            "SMTP_FROM": "smtp-from@example.com",
            "EMAIL_TO": "   ",
            "SMTP_TO": "alias@example.com",
        }
    )
    assert aliases.sender == "smtp-from@example.com"
    assert aliases.recipients == ("alias@example.com",)


@pytest.mark.parametrize(
    ("value", "expected_mode", "expected_port"),
    [("SSL", "ssl", 465), ("startTLS", "starttls", 587), ("TLS", "starttls", 587), ("none", "none", 25)],
)
def test_smtp_security_modes_are_case_insensitive(value, expected_mode, expected_port):
    config = resolve_smtp_config({**BASE, "SMTP_SECURITY": value})
    assert config.security == expected_mode
    assert config.port == expected_port


def test_smtp_security_overrides_legacy_flag_and_legacy_remains_supported():
    preferred = resolve_smtp_config({**BASE, "SMTP_SECURITY": "tls", "SMTP_USE_SSL": "true"})
    legacy = resolve_smtp_config({**BASE, "SMTP_USE_SSL": "false"})
    assert preferred.security == "starttls"
    assert preferred.port == 587
    assert legacy.security == "starttls"


def test_smtp_rejects_unknown_security_and_requires_explicit_recipient():
    with pytest.raises(RuntimeError, match="SMTP_SECURITY must be one of"):
        resolve_smtp_config({**BASE, "SMTP_SECURITY": "opportunistic"})
    without_recipient = {key: value for key, value in BASE.items() if key != "EMAIL_TO"}
    with pytest.raises(RuntimeError, match="explicit EMAIL_TO/SMTP_TO"):
        resolve_smtp_config(without_recipient)
