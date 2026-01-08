"""Custom exceptions for consistent error handling."""
from typing import Optional, List, Dict


class CARException(Exception):
    """Base exception for all CAR Platform errors."""
    
    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[List[Dict[str, str]]] = None,
    ):
        """
        Initialize CAR exception.
        
        Args:
            code: Error code (e.g., "VALIDATION_ERROR")
            message: Human-readable error message
            details: Optional list of field-specific error details
        """
        self.code = code
        self.message = message
        self.details = details or []
        super().__init__(self.message)


class ValidationError(CARException):
    """Raised when request validation fails (400)."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[List[Dict[str, str]]] = None,
    ):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class AuthenticationError(CARException):
    """Raised when authentication fails (401)."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            code="AUTHENTICATION_ERROR",
            message=message,
        )


class PermissionError(CARException):
    """Raised when user lacks required permissions (403)."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            code="PERMISSION_ERROR",
            message=message,
        )


class NotFoundError(CARException):
    """Raised when a resource is not found (404)."""
    
    def __init__(self, resource_type: str = "Resource", resource_id: Optional[str] = None):
        message = f"{resource_type} not found"
        if resource_id:
            message = f"{resource_type} '{resource_id}' not found"
        
        super().__init__(
            code="NOT_FOUND",
            message=message,
        )


class RateLimitError(CARException):
    """Raised when rate limit is exceeded (429)."""
    
    def __init__(self, retry_after: int, message: Optional[str] = None):
        if message is None:
            message = f"Rate limit exceeded. Retry after {retry_after} seconds"
        
        super().__init__(
            code="RATE_LIMIT_ERROR",
            message=message,
        )
        self.retry_after = retry_after
