# Troubleshooting Guide

## Common Issues and Solutions

### 1. MongoDB Connection Refused

**Error:**
```text
Failed to connect to MongoDB: localhost:27017: [Errno 61] Connection refused
```

**Cause:** MongoDB is not running locally.

**Solutions:**

#### Option 1: Docker (Recommended)
```bash
docker-compose up -d mongodb
docker-compose ps
```

#### Option 2: Local MongoDB via Homebrew (macOS)
```bash
brew services start mongodb-community
brew services list | grep mongodb
```

#### Option 3: MongoDB Atlas (Cloud)
Set `MONGODB_URI` in your `ai-service/.env` file.

---

### 2. Port 8001 Already in Use

**Error:**
```text
ERROR: [Errno 48] Address already in use
```

**Solution:**
```bash
lsof -ti:8001 | xargs kill -9
```

---

### 3. Redis Connection Warning

**Warning:**
```text
Redis connection failed. Continuing without cache...
```

**Solution:**
Start Redis via Docker:
```bash
docker-compose up -d redis
```
*Note: Redis is optional for local development; the AI service continues without caching if unavailable.*

---

### 4. Module Not Found Error

**Error:**
```text
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:**
Ensure you are using the virtual environment:
```bash
cd ai-service && source venv/bin/activate
venv/bin/python3 -m pip install -r requirements.txt
```

---

### 5. Health & Readiness Check

Verify the AI service is healthy on port 8001:
```bash
curl -H "X-Visual-Tutor-Internal-Token: visual-tutor-dev-token" \
     -H "X-Visual-Tutor-User-Id: test-user" \
     http://localhost:8001/api/v1/visual_tutor/readiness
```

---

### 6. Docker Commands

```bash
# Start required databases
docker-compose up -d mongodb redis

# View logs
docker-compose logs -f

# Stop containers
docker-compose down
```
