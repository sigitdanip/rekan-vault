from rekanvault.contracts.errors import (
    ErrorCode,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


def test_error_envelope_creation():
    err = NotFoundError("Document not found", target="doc_12345", details={"key": "val"})
    envelope = err.to_envelope(request_id="req_test_001")

    assert envelope.request_id == "req_test_001"
    assert envelope.error.code == ErrorCode.NOT_FOUND
    assert envelope.error.message == "Document not found"
    assert envelope.error.target == "doc_12345"
    assert envelope.error.details == {"key": "val"}


def test_unauthorized_and_validation_errors():
    unauth = UnauthorizedError("Invalid OAuth token")
    assert unauth.code == ErrorCode.UNAUTHORIZED

    val_err = ValidationError("Missing workspace_id")
    assert val_err.code == ErrorCode.VALIDATION_ERROR
