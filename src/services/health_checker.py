"""Health check service for monitoring system components."""
import time
import logging
import asyncio
import httpx
from typing import Any, Dict, Literal, Optional
from supabase import Client

from src.auth.config import get_auth_config
from src.auth.client import create_service_client

logger = logging.getLogger(__name__)

CHECK_TIMEOUT_SECONDS = 5.0

Status = Literal["up", "down"]


class HealthCheckResult:
    """Result of a single health check."""
    
    def __init__(self, status: Status, latency_ms: int, error: Optional[str] = None):
        self.status = status
        self.latency_ms = latency_ms
        self.error = error
    
    def to_dict(self) -> Dict[str, str | int]:
        """Convert to dictionary for API response."""
        result: Dict[str, str | int] = {
            "status": self.status,
            "latency_ms": self.latency_ms,
        }
        if self.error:
            result["error"] = self.error
        return result


class HealthChecker:
    """Service for checking health of system components."""
    
    def __init__(self) -> None:
        """Initialize health checker with service client."""
        self.config = get_auth_config()
        self.service_client: Client | None = None
    
    def _get_service_client(self) -> Client:
        """Get or create service client for health checks."""
        if self.service_client is None:
            self.service_client = create_service_client(self.config)
        return self.service_client
    
    async def check_database(self) -> HealthCheckResult:
        """
        Check database connectivity.
        
        Performs a simple query to verify database is accessible.
        Times out after CHECK_TIMEOUT_SECONDS.
        """
        start_time = time.time()
        
        def _check() -> Any:
            client = self._get_service_client()
            # Simple query to check database connectivity
            # Using a lightweight query that doesn't require specific tables
            result = client.table("tenants").select("id").limit(1).execute()
            return result
        
        try:
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, _check),
                timeout=CHECK_TIMEOUT_SECONDS,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(status="up", latency_ms=latency_ms)
            
        except asyncio.TimeoutError:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.warning("Database health check timed out")
            return HealthCheckResult(status="down", latency_ms=latency_ms, error="Timeout")
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            logger.warning(f"Database health check failed: {error_msg}")
            return HealthCheckResult(status="down", latency_ms=latency_ms, error=error_msg)
    
    async def check_storage(self) -> HealthCheckResult:
        """
        Check storage service connectivity.
        
        Verifies that Supabase Storage API is accessible.
        Times out after CHECK_TIMEOUT_SECONDS.
        """
        start_time = time.time()
        
        def _check() -> Any:
            client = self._get_service_client()
            # Try to list buckets (lightweight operation)
            # This verifies storage API is accessible
            buckets = client.storage.list_buckets()
            return buckets
        
        try:
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, _check),
                timeout=CHECK_TIMEOUT_SECONDS,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(status="up", latency_ms=latency_ms)
            
        except asyncio.TimeoutError:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.warning("Storage health check timed out")
            return HealthCheckResult(status="down", latency_ms=latency_ms, error="Timeout")
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            logger.warning(f"Storage health check failed: {error_msg}")
            return HealthCheckResult(status="down", latency_ms=latency_ms, error=error_msg)
    
    async def check_auth(self) -> HealthCheckResult:
        """
        Check authentication service connectivity.
        
        Verifies that Supabase Auth API is accessible by checking the health endpoint.
        """
        start_time = time.time()
        
        try:
            auth_url = f"{self.config.supabase_url.rstrip('/')}/auth/v1/health"
            
            async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_SECONDS) as http_client:
                response = await http_client.get(auth_url)
                
                # If we get any response (even 404), auth service is reachable
                # 200 = healthy, 404 = endpoint doesn't exist but service is up
                if response.status_code in (200, 404):
                    latency_ms = int((time.time() - start_time) * 1000)
                    return HealthCheckResult(status="up", latency_ms=latency_ms)
                else:
                    latency_ms = int((time.time() - start_time) * 1000)
                    return HealthCheckResult(
                        status="down",
                        latency_ms=latency_ms,
                        error=f"Auth service returned {response.status_code}",
                    )
            
        except httpx.TimeoutException:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.warning("Auth health check timed out")
            return HealthCheckResult(
                status="down",
                latency_ms=latency_ms,
                error="Timeout",
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            logger.warning(f"Auth health check failed: {error_msg}")
            return HealthCheckResult(status="down", latency_ms=latency_ms, error=error_msg)
    
    async def check_presidio(self) -> HealthCheckResult:
        """
        Check Presidio redaction service.
        
        Verifies that Presidio analyzer and anonymizer are initialized.
        """
        start_time = time.time()
        
        try:
            from src.services.redaction import _get_analyzer, _get_anonymizer
            
            # Verify Presidio is initialized
            analyzer = _get_analyzer()
            _get_anonymizer()
            
            # Perform a simple test redaction to verify functionality
            test_text = "Test email: test@example.com"
            analyzer.analyze(text=test_text, language="en")
            
            latency_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(status="up", latency_ms=latency_ms)
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            logger.warning(f"Presidio health check failed: {error_msg}")
            return HealthCheckResult(status="down", latency_ms=latency_ms, error=error_msg)
    
    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """
        Check all system components.
        
        Returns:
            Dictionary mapping component names to health check results
        """
        # Run all checks concurrently for faster response
        results = list(
            await asyncio.gather(
                self.check_database(),
                self.check_storage(),
                self.check_auth(),
                self.check_presidio(),
                return_exceptions=True,
            )
        )
        
        # Handle any exceptions
        checks: Dict[str, HealthCheckResult] = {}
        component_names = ["database", "storage", "auth", "presidio"]
        
        for i, result in enumerate(results):
            component = component_names[i]
            if isinstance(result, BaseException):
                checks[component] = HealthCheckResult(
                    status="down",
                    latency_ms=0,
                    error=str(result),
                )
            else:
                checks[component] = result
        
        return checks
    
    def get_overall_status(self, checks: Dict[str, HealthCheckResult]) -> Literal["healthy", "unhealthy"]:
        """
        Determine overall system status from individual checks.
        
        Args:
            checks: Dictionary of component health check results
            
        Returns:
            "healthy" if all checks pass
            "unhealthy" if any critical check fails
        """
        if all(check.status == "up" for check in checks.values()):
            return "healthy"
        # All components are critical, so any failure = unhealthy
        return "unhealthy"
