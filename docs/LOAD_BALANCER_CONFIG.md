# Load Balancer Health Check Configuration

This document provides configuration examples for configuring load balancers to use the `/health/ready` endpoint for health checks.

## Health Check Endpoints

- **Liveness**: `GET /health` - Simple check that service is running (200 OK)
- **Readiness**: `GET /health/ready` - Comprehensive check of all dependencies (200 OK if healthy, 503 if unhealthy)

**Recommended**: Use `/health/ready` for load balancer health checks to ensure traffic is only routed to healthy instances.

## Configuration Examples

### AWS Application Load Balancer (ALB)

```json
{
  "HealthCheckPath": "/health/ready",
  "HealthCheckProtocol": "HTTP",
  "HealthCheckPort": "traffic-port",
  "HealthCheckIntervalSeconds": 30,
  "HealthCheckTimeoutSeconds": 5,
  "HealthyThresholdCount": 2,
  "UnhealthyThresholdCount": 3,
  "Matcher": {
    "HttpCode": "200"
  }
}
```

**Terraform Example:**
```hcl
resource "aws_lb_target_group" "app" {
  name     = "car-platform-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health/ready"
    protocol            = "HTTP"
    matcher             = "200"
  }
}
```

### AWS Elastic Load Balancer (ELB Classic)

```json
{
  "HealthCheck": {
    "Target": "HTTP:8000/health/ready",
    "Interval": 30,
    "Timeout": 5,
    "UnhealthyThreshold": 3,
    "HealthyThreshold": 2
  }
}
```

### Nginx

```nginx
upstream car_platform {
    least_conn;
    server app1:8000 max_fails=3 fail_timeout=30s;
    server app2:8000 max_fails=3 fail_timeout=30s;
    server app3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://car_platform;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Health check endpoint (for monitoring)
    location /health/ready {
        proxy_pass http://car_platform/health/ready;
        access_log off;
    }
}
```

**With active health checks (Nginx Plus):**
```nginx
upstream car_platform {
    least_conn;
    server app1:8000;
    server app2:8000;
    server app3:8000;
    
    # Active health checks
    health_check uri=/health/ready interval=30s fails=3 passes=2;
}
```

### Traefik

```yaml
# docker-compose.yml or traefik.yml
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
    labels:
      - "traefik.http.services.car-platform.loadbalancer.healthcheck.path=/health/ready"
      - "traefik.http.services.car-platform.loadbalancer.healthcheck.interval=30s"
      - "traefik.http.services.car-platform.loadbalancer.healthcheck.timeout=5s"
```

**Static Configuration:**
```yaml
http:
  services:
    car-platform:
      loadBalancer:
        healthCheck:
          path: /health/ready
          interval: 30s
          timeout: 5s
          scheme: http
```

### Kubernetes

**Deployment with Readiness Probe:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: car-platform
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: app
        image: car-platform:latest
        ports:
        - containerPort: 8000
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
          successThreshold: 1
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 60
          timeoutSeconds: 5
          failureThreshold: 3
```

**Service:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: car-platform
spec:
  selector:
    app: car-platform
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Google Cloud Load Balancer

```yaml
# gcloud command
gcloud compute health-checks create http car-platform-health \
  --port=8000 \
  --request-path=/health/ready \
  --check-interval=30s \
  --timeout=5s \
  --healthy-threshold=2 \
  --unhealthy-threshold=3
```

**Terraform:**
```hcl
resource "google_compute_health_check" "car_platform" {
  name               = "car-platform-health"
  check_interval_sec = 30
  timeout_sec        = 5
  healthy_threshold  = 2
  unhealthy_threshold = 3

  http_health_check {
    port         = 8000
    request_path = "/health/ready"
  }
}
```

### Azure Load Balancer

```json
{
  "properties": {
    "probe": {
      "protocol": "Http",
      "port": 8000,
      "requestPath": "/health/ready",
      "intervalInSeconds": 30,
      "numberOfProbes": 3
    }
  }
}
```

**ARM Template:**
```json
{
  "type": "Microsoft.Network/loadBalancers/probes",
  "apiVersion": "2021-05-01",
  "name": "car-platform-probe",
  "properties": {
    "protocol": "Http",
    "port": 8000,
    "requestPath": "/health/ready",
    "intervalInSeconds": 30,
    "numberOfProbes": 3
  }
}
```

### HAProxy

```haproxy
global
    log stdout local0

defaults
    mode http
    timeout connect 5s
    timeout client 30s
    timeout server 30s

frontend http_front
    bind *:80
    default_backend car_platform_backend

backend car_platform_backend
    balance roundrobin
    option httpchk GET /health/ready
    http-check expect status 200
    server app1 app1:8000 check inter 30s fall 3 rise 2
    server app2 app2:8000 check inter 30s fall 3 rise 2
    server app3 app3:8000 check inter 30s fall 3 rise 2
```

## Health Check Response

### Healthy Response (200 OK)
```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "status": "up",
      "latency_ms": 5
    },
    "storage": {
      "status": "up",
      "latency_ms": 12
    },
    "auth": {
      "status": "up",
      "latency_ms": 8
    }
  },
  "version": "1.0.0"
}
```

### Unhealthy Response (503 Service Unavailable)
```json
{
  "status": "unhealthy",
  "checks": {
    "database": {
      "status": "down",
      "latency_ms": 5000,
      "error": "Connection timeout"
    },
    "storage": {
      "status": "up",
      "latency_ms": 12
    },
    "auth": {
      "status": "up",
      "latency_ms": 8
    }
  },
  "version": "1.0.0"
}
```

## Recommended Settings

- **Interval**: 30 seconds (balance between responsiveness and load)
- **Timeout**: 5 seconds (matches health check timeout)
- **Healthy Threshold**: 2 consecutive successes
- **Unhealthy Threshold**: 3 consecutive failures
- **Expected Status Code**: 200 (for healthy), 503 (for unhealthy)

## Notes

1. **No Authentication Required**: Health check endpoints are public and do not require authentication
2. **Timeout**: Health checks have a 5-second timeout per service check
3. **Concurrent Checks**: All service checks run concurrently for faster response
4. **Status Codes**: 
   - `200 OK` = All services healthy
   - `503 Service Unavailable` = One or more critical services down

## Monitoring

You can also use `/health/ready` for external monitoring tools:

```bash
# Example monitoring script
curl -f http://api.example.com/health/ready || alert "Service unhealthy"
```
