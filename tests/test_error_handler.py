"""Tests for error handler middleware."""
import json
import pytest
from typing import Any, Generator
from unittest.mock import Mock, AsyncMock
from fastapi import Request, HTTPException

from src.middleware.error_handler import ErrorHandlerMiddleware
from src.exceptions import (
    ValidationError,
    AuthenticationError,
    PermissionError,
    NotFoundError,
    RateLimitError,
    CARException,
)


class TestErrorHandlerMiddleware:
    """Test error handler middleware error responses."""

    @pytest.fixture
    def middleware(self) -> Any:
        """Create middleware instance."""
        return ErrorHandlerMiddleware(app=Mock())

    @pytest.fixture
    def mock_request(self) -> Any:
        """Create mock request."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.request_id = "test-request-123"
        return request

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, middleware, mock_request) -> None:
        """Test handling of custom ValidationError."""
        exc = ValidationError("Invalid input", details=["field1", "field2"])

        response = middleware._handle_car_exception(exc, "test-request-123")

        assert response.status_code == 400
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["message"] == "Invalid input"

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, middleware, mock_request) -> None:
        """Test handling of AuthenticationError."""
        exc = AuthenticationError("Invalid token")

        response = middleware._handle_car_exception(exc, "test-request-123")

        assert response.status_code == 401
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "AUTHENTICATION_ERROR"
        assert body["error"]["message"] == "Invalid token"

    @pytest.mark.asyncio
    async def test_permission_error_handling(self, middleware, mock_request) -> None:
        """Test handling of PermissionError."""
        exc = PermissionError("Access denied")

        response = middleware._handle_car_exception(exc, "test-request-123")

        assert response.status_code == 403
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "PERMISSION_ERROR"
        assert body["error"]["message"] == "Access denied"

    @pytest.mark.asyncio
    async def test_not_found_error_handling(self, middleware, mock_request) -> None:
        """Test handling of NotFoundError."""
        exc = NotFoundError("Resource")

        response = middleware._handle_car_exception(exc, "test-request-123")

        assert response.status_code == 404
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "NOT_FOUND"
        assert "not found" in body["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, middleware, mock_request) -> None:
        """Test handling of RateLimitError."""
        exc = RateLimitError(retry_after=60, message="Rate limit exceeded")

        response = middleware._handle_car_exception(exc, "test-request-123")

        assert response.status_code == 429
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "RATE_LIMIT_ERROR"
        assert body["error"]["message"] == "Rate limit exceeded"
        assert body["error"]["retry_after"] == 60

    @pytest.mark.asyncio
    async def test_http_exception_with_string_detail(self, middleware, mock_request) -> None:
        """Test handling of HTTPException with string detail."""
        exc = HTTPException(status_code=404, detail="Resource not found")

        response = middleware._handle_http_exception(exc, "test-request-123")

        assert response.status_code == 404
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "HTTP_ERROR"
        assert body["error"]["message"] == "Resource not found"

    @pytest.mark.asyncio
    async def test_http_exception_with_dict_detail(self, middleware, mock_request) -> None:
        """Test handling of HTTPException with dict detail."""
        exc = HTTPException(
            status_code=400,
            detail={
                "code": "CUSTOM_ERROR",
                "message": "Custom error message",
                "details": [{"field": "test", "issue": "invalid"}],
            },
        )

        response = middleware._handle_http_exception(exc, "test-request-123")

        assert response.status_code == 400
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "CUSTOM_ERROR"
        assert body["error"]["message"] == "Custom error message"
        assert body["error"]["details"] == [{"field": "test", "issue": "invalid"}]

    @pytest.mark.asyncio
    async def test_http_exception_with_no_detail(self, middleware, mock_request) -> None:
        """Test handling of HTTPException with no detail."""
        exc = HTTPException(status_code=500)

        response = middleware._handle_http_exception(exc, "test-request-123")

        assert response.status_code == 500
        body = json.loads(response.body.decode())
        # HTTPException with no detail defaults to status text or "An error occurred"
        assert body["error"]["message"] in ["Internal Server Error", "An error occurred"]

    @pytest.mark.asyncio
    async def test_unhandled_exception_handling(self, middleware, mock_request) -> None:
        """Test handling of unhandled exceptions."""
        exc = ValueError("Unexpected error")

        response = middleware._handle_unhandled_exception(
            exc, "test-request-123"
        )

        assert response.status_code == 500
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert body["error"]["message"] == "An unexpected error occurred"
        # Should not expose internal details
        assert "ValueError" not in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_request_validation_error_handling(self, middleware, mock_request) -> None:
        """Test handling of FastAPI validation errors."""

        # Create a mock RequestValidationError
        class MockValidationError:
            def __init__(self):
                pass

            def errors(self):
                return [
                    {"loc": ("body", "name"), "msg": "field required"},
                    {"loc": ("body", "price"), "msg": "value must be greater than 0"},
                ]

        exc = MockValidationError()

        response = middleware._handle_validation_error(exc, "test-request-123")

        assert response.status_code == 400
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["message"] == "Request validation failed"
        assert len(body["error"]["details"]) == 2

    @pytest.mark.asyncio
    async def test_unknown_car_exception_returns_500(self, middleware, mock_request) -> None:
        """Test that unknown CARException types return 500."""

        class UnknownCARException(CARException):
            """Custom exception not in status code map."""

            pass

        exc = UnknownCARException(code="UNKNOWN_ERROR", message="Unknown error")

        response = middleware._handle_car_exception(exc, "test-request-123")

        assert response.status_code == 500
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "UNKNOWN_ERROR"

    @pytest.mark.asyncio
    async def test_http_exception_preserves_status_code(self, middleware, mock_request) -> None:
        """Test that HTTPException status codes are preserved correctly."""
        test_cases = [
            (400, "Bad Request"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
            (404, "Not Found"),
            (409, "Conflict"),
            (422, "Unprocessable Entity"),
        ]

        for status_code, message in test_cases:
            exc = HTTPException(status_code=status_code, detail=message)
            response = middleware._handle_http_exception(
                exc, "test-request-123"
            )
            assert response.status_code == status_code

    @pytest.mark.asyncio
    async def test_request_id_included_in_error(self, middleware, mock_request) -> None:
        """Test that request ID is included in error responses."""
        exc = ValidationError("Test error")
        request_id = "custom-request-789"

        response = middleware._handle_car_exception(exc, request_id)

        body = json.loads(response.body.decode())
        assert body["error"]["request_id"] == request_id

    @pytest.mark.asyncio
    async def test_dispatch_successful_request(self, middleware, mock_request) -> None:
        """Test that successful requests pass through middleware."""
        mock_response = Mock()
        call_next = AsyncMock(return_value=mock_response)

        result = await middleware.dispatch(mock_request, call_next)

        assert result == mock_response
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_handles_exception(self, middleware, mock_request) -> None:
        """Test that dispatch handles exceptions from call_next."""
        exc = ValidationError("Test error")
        call_next = AsyncMock(side_effect=exc)

        response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 400
        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_request_id_from_request_state(self, middleware) -> None:
        """Test extracting request ID from request state."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.request_id = "state-request-id"

        exc = ValidationError("Test error")
        call_next = AsyncMock(side_effect=exc)

        response = await middleware.dispatch(request, call_next)

        body = json.loads(response.body.decode())
        assert body["error"]["request_id"] == "state-request-id"

    @pytest.mark.asyncio
    async def test_missing_request_id_handled(self, middleware) -> None:
        """Test handling when request doesn't have request_id in state."""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])  # No request_id attribute

        exc = ValidationError("Test error")
        call_next = AsyncMock(side_effect=exc)

        response = await middleware.dispatch(request, call_next)

        body = json.loads(response.body.decode())
        assert body["error"]["request_id"] is None
