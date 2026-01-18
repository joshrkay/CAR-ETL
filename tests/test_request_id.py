"""Tests for request ID middleware."""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import uuid

from src.middleware.request_id import RequestIDMiddleware
from typing import Any


class TestRequestIDMiddleware:
    """Test request ID middleware functionality."""

    def test_generates_request_id_when_not_provided(self) -> None:
        """Test that middleware generates a request ID when not provided by client."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request) -> Any:
            return {"request_id": request.state.request_id}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        request_id = response.json()["request_id"]

        # Should be a valid UUID
        assert request_id is not None
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Generated request_id '{request_id}' is not a valid UUID")

    def test_uses_client_provided_request_id(self) -> None:
        """Test that middleware uses client-provided request ID."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request) -> Any:
            return {"request_id": request.state.request_id}

        client = TestClient(app)
        custom_request_id = "custom-request-12345"
        response = client.get("/test", headers={"X-Request-ID": custom_request_id})

        assert response.status_code == 200
        assert response.json()["request_id"] == custom_request_id

    def test_adds_request_id_to_response_header(self) -> None:
        """Test that middleware adds request ID to response headers."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint() -> Any:
            return {"message": "success"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]

        # Should be a valid UUID
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Response header request_id '{request_id}' is not a valid UUID")

    def test_preserves_client_request_id_in_response_header(self) -> None:
        """Test that client-provided request ID appears in response header."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint() -> Any:
            return {"message": "success"}

        client = TestClient(app)
        custom_request_id = "my-custom-id-789"
        response = client.get("/test", headers={"X-Request-ID": custom_request_id})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == custom_request_id

    def test_request_id_available_in_request_state(self) -> None:
        """Test that request ID is stored in request.state."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        captured_request_id = None

        @app.get("/test")
        async def test_endpoint(request: Request) -> Any:
            nonlocal captured_request_id
            captured_request_id = request.state.request_id
            return {"message": "success"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert captured_request_id is not None
        assert response.headers["X-Request-ID"] == captured_request_id

    def test_different_requests_get_different_ids(self) -> None:
        """Test that different requests get different request IDs."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request) -> Any:
            return {"request_id": request.state.request_id}

        client = TestClient(app)

        response1 = client.get("/test")
        response2 = client.get("/test")

        request_id1 = response1.json()["request_id"]
        request_id2 = response2.json()["request_id"]

        assert request_id1 != request_id2

    def test_request_id_survives_error_responses(self) -> None:
        """Test that request ID is preserved even when endpoint raises error."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint() -> Any:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="Test error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        # Should still have request ID in header even on error
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] is not None

    def test_request_id_with_post_request(self) -> None:
        """Test request ID generation works with POST requests."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.post("/test")
        async def test_endpoint(request: Request) -> Any:
            return {"request_id": request.state.request_id}

        client = TestClient(app)
        response = client.post("/test", json={"data": "test"})

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        request_id = response.json()["request_id"]
        assert request_id == response.headers["X-Request-ID"]

    def test_request_id_with_various_http_methods(self) -> None:
        """Test request ID works with various HTTP methods."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def get_endpoint(request: Request) -> Any:
            return {"method": "GET", "request_id": request.state.request_id}

        @app.post("/test")
        async def post_endpoint(request: Request) -> Any:
            return {"method": "POST", "request_id": request.state.request_id}

        @app.put("/test")
        async def put_endpoint(request: Request) -> Any:
            return {"method": "PUT", "request_id": request.state.request_id}

        @app.delete("/test")
        async def delete_endpoint(request: Request) -> Any:
            return {"method": "DELETE", "request_id": request.state.request_id}

        client = TestClient(app)

        for method in ["get", "post", "put", "delete"]:
            response = getattr(client, method)("/test")
            assert response.status_code == 200
            assert "X-Request-ID" in response.headers
            assert response.json()["request_id"] is not None

    def test_request_id_format_validation(self) -> None:
        """Test that generated request IDs are valid UUIDs."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request) -> Any:
            return {"request_id": request.state.request_id}

        client = TestClient(app)

        # Test multiple requests to ensure consistent format
        for _ in range(5):
            response = client.get("/test")
            request_id = response.json()["request_id"]

            # Should be valid UUID
            uuid_obj = uuid.UUID(request_id)
            # Should be UUID version 4
            assert uuid_obj.version == 4
