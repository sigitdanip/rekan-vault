from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    target: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
    request_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class RekanVaultError(Exception):
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        target: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.target = target
        self.details = details or {}

    def to_envelope(self, request_id: str) -> ErrorEnvelope:
        return ErrorEnvelope(
            error=ErrorDetail(
                code=self.code,
                message=self.message,
                target=self.target,
                details=self.details,
            ),
            request_id=request_id,
        )


class NotFoundError(RekanVaultError):
    def __init__(self, message: str, target: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, code=ErrorCode.NOT_FOUND, target=target, details=details)


class UnauthorizedError(RekanVaultError):
    def __init__(self, message: str, target: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, code=ErrorCode.UNAUTHORIZED, target=target, details=details)


class ValidationError(RekanVaultError):
    def __init__(self, message: str, target: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, code=ErrorCode.VALIDATION_ERROR, target=target, details=details)


class ProviderError(RekanVaultError):
    def __init__(self, message: str, target: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, code=ErrorCode.PROVIDER_ERROR, target=target, details=details)


class PermissionError(RekanVaultError):
    def __init__(self, message: str, target: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, code=ErrorCode.FORBIDDEN, target=target, details=details)
