# Kafka/Redpanda Setup for Windows

## Quick Setup Options

### Option 1: Docker (Recommended - Easiest)

**Redpanda (Recommended for Development):**

```powershell
# Pull Redpanda image
docker pull docker.redpanda.com/redpandadata/redpanda:latest

# Start Redpanda container
docker run -d --name redpanda `
  -p 8081:8081 `
  -p 8082:8082 `
  -p 9092:9092 `
  -p 9644:9644 `
  docker.redpanda.com/redpandadata/redpanda:latest redpanda start `
  --kafka-addr internal://0.0.0.0:9092,external://0.0.0.0:19092 `
  --advertise-kafka-addr internal://redpanda:9092,external://localhost:19092 `
  --pandaproxy-addr internal://0.0.0.0:8082,external://0.0.0.0:18082 `
  --advertise-pandaproxy-addr internal://redpanda:8082,external://localhost:18082 `
  --schema-registry-addr internal://0.0.0.0:8081,external://0.0.0.0:18081 `
  --advertise-schema-registry-addr internal://redpanda:8081,external://localhost:18081 `
  --rpc-addr redpanda:33145 `
  --advertise-rpc-addr redpanda:33145 `
  --smp 1 `
  --memory 1G `
  --mode dev-container `
  --default-log-level=info
```

**Or use Docker Compose (Easier):**

Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  redpanda:
    image: docker.redpanda.com/redpandadata/redpanda:latest
    container_name: redpanda
    command:
      - redpanda
      - start
      - --kafka-addr
      - internal://0.0.0.0:9092,external://0.0.0.0:19092
      - --advertise-kafka-addr
      - internal://redpanda:9092,external://localhost:19092
      - --pandaproxy-addr
      - internal://0.0.0.0:8082,external://0.0.0.0:18082
      - --advertise-pandaproxy-addr
      - internal://redpanda:8082,external://localhost:18082
      - --schema-registry-addr
      - internal://0.0.0.0:8081,external://0.0.0.0:18081
      - --advertise-schema-registry-addr
      - internal://redpanda:8081,external://localhost:18081
      - --rpc-addr
      - redpanda:33145
      - --advertise-rpc-addr
      - redpanda:33145
      - --smp
      - '1'
      - --memory
      - 1G
      - --mode
      - dev-container
    ports:
      - "18081:18081"
      - "18082:18082"
      - "19092:19092"
      - "19644:9644"
    volumes:
      - redpanda-data:/var/lib/redpanda/data
volumes:
  redpanda-data:
```

Then run:
```powershell
docker-compose up -d
```

**Note:** Update `KAFKA_BOOTSTRAP_SERVERS=localhost:19092` for Docker setup.

---

### Option 2: Install Redpanda Binary (Windows)

1. Download Redpanda from: https://github.com/redpanda-data/redpanda/releases
2. Extract to a directory (e.g., `C:\redpanda`)
3. Add to PATH or run directly:

```powershell
# Navigate to Redpanda directory
cd C:\redpanda

# Start Redpanda
.\rpk.exe redpanda start --smp 1 --memory 1G --mode dev
```

---

### Option 3: Install Apache Kafka (Windows)

1. Download Kafka from: https://kafka.apache.org/downloads
2. Extract to a directory (e.g., `C:\kafka`)
3. Start Zookeeper (required for Kafka):

```powershell
cd C:\kafka
.\bin\windows\zookeeper-server-start.bat .\config\zookeeper.properties
```

4. In a new terminal, start Kafka:

```powershell
cd C:\kafka
.\bin\windows\kafka-server-start.bat .\config\server.properties
```

---

## Verify Installation

Once Kafka/Redpanda is running, verify it's accessible:

```powershell
# Test connection (if you have kafka tools installed)
kafka-topics --bootstrap-server localhost:9092 --list

# Or use our Python script
python scripts/setup_ingestion_topic.py
```

---

## Environment Variables

Set these environment variables:

```powershell
# For local Redpanda/Kafka
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
$env:INGESTION_TOPIC = "ingestion-events"

# For Docker Redpanda (port 19092)
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:19092"
```

Or create/update `.env` file:
```
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
INGESTION_TOPIC=ingestion-events
```

---

## Create Topics

Once Kafka/Redpanda is running:

```powershell
python scripts/setup_ingestion_topic.py
```

This will create:
- `ingestion-events` topic (6 partitions, 7-day retention)
- `ingestion-events-dlq` topic (3 partitions, 30-day retention)

---

## Troubleshooting

### Port Already in Use

If port 9092 is already in use:

```powershell
# Find process using port 9092
netstat -ano | findstr :9092

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### Connection Refused

- Ensure Kafka/Redpanda is running
- Check firewall settings
- Verify port is correct (9092 for local, 19092 for Docker)

### Docker Issues

```powershell
# Check if container is running
docker ps

# View logs
docker logs redpanda

# Restart container
docker restart redpanda
```

---

## Recommended: Docker Compose Setup

For the easiest setup, use Docker Compose. Create `docker-compose.yml` in project root and run:

```powershell
docker-compose up -d
```

This starts Redpanda with all necessary ports exposed and ready to use.
