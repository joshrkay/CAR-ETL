# CAR Platform Deployment Guide

## Health Check Endpoints

The CAR Platform provides two health check endpoints for load balancer configuration:

### Liveness Check
- **Endpoint**: `GET /health`
- **Purpose**: Simple check that the service is running
- **Response**: `200 OK` with `{"status": "healthy"}`
- **Use Case**: Container orchestration liveness probes

### Readiness Check
- **Endpoint**: `GET /health/ready`
- **Purpose**: Comprehensive check of all system dependencies
- **Response**: 
  - `200 OK` if all services are healthy
  - `503 Service Unavailable` if any critical service is down
- **Use Case**: Load balancer health checks, readiness probes

**Recommended**: Use `/health/ready` for load balancer health checks.

## Quick Start

### Environment Variables

Create a `.env` file with:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
SUPABASE_JWT_SECRET=your-jwt-secret
APP_ENV=production
```

### Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
# Build image
docker build -t car-platform:latest .

# Run container
docker run -p 8000:8000 --env-file .env car-platform:latest
```

### Kubernetes

See `deployment/load-balancer-config.yaml` for complete Kubernetes deployment examples.

## Load Balancer Configuration

See `docs/LOAD_BALANCER_CONFIG.md` for detailed configuration examples for:
- AWS Application Load Balancer (ALB)
- AWS Elastic Load Balancer (ELB)
- Nginx
- Traefik
- Kubernetes
- Google Cloud Load Balancer
- Azure Load Balancer
- HAProxy

## Health Check Response Format

### Healthy Response (200 OK)
```json
{
  "status": "healthy",
  "checks": {
    "database": {"status": "up", "latency_ms": 5},
    "storage": {"status": "up", "latency_ms": 12},
    "auth": {"status": "up", "latency_ms": 8}
  },
  "version": "1.0.0"
}
```

### Unhealthy Response (503 Service Unavailable)
```json
{
  "status": "unhealthy",
  "checks": {
    "database": {"status": "down", "latency_ms": 5000, "error": "Connection timeout"},
    "storage": {"status": "up", "latency_ms": 12},
    "auth": {"status": "up", "latency_ms": 8}
  },
  "version": "1.0.0"
}
```

## Recommended Load Balancer Settings

- **Health Check Path**: `/health/ready`
- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Healthy Threshold**: 2 consecutive successes
- **Unhealthy Threshold**: 3 consecutive failures
- **Expected Status Code**: 200 (for healthy instances)

## Notes

1. Health check endpoints are **public** (no authentication required)
2. Each service check has a 5-second timeout
3. All service checks run concurrently for faster response
4. Any critical service failure results in `503 Service Unavailable`
