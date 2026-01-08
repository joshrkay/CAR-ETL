"""
Tenant context middleware.

This module provides middleware for setting up tenant context per request.
The actual implementation is in src.auth.middleware.AuthMiddleware which:
1. Validates JWT tokens
2. Extracts tenant context
3. Creates Supabase client with user's JWT for RLS enforcement
4. Attaches to request.state

This file exists for organizational purposes and documentation.
"""

# The actual implementation is in src.auth.middleware.AuthMiddleware
# Import here for convenience
from src.auth.middleware import AuthMiddleware

__all__ = ["AuthMiddleware"]
