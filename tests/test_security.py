"""Unit tests for security checkpoint validation and redaction."""


def test_security_import():
    """Verify that security modules can be imported without errors."""
    from backend.security import input_validator, pii_redactor

    assert input_validator is not None
    assert pii_redactor is not None
