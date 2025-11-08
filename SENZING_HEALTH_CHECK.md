# Senzing Health Check Guide

Quick guide to verify your Senzing entity resolution setup is working correctly.

## Quick Check (Easiest)

**Run the diagnostic script:**
```bash
./check_senzing.sh
```

**What it checks:**
- ✅ API availability
- ✅ Senzing SDK installed
- ✅ License configured
- ✅ gRPC connection working
- ✅ Database connectivity

**Expected output:**
```
✅ Senzing Status: HEALTHY

Your Senzing setup is working correctly!
```

---

## API Health Check Endpoint

**Check via API:**
```bash
curl http://localhost:8000/api/entity-resolution/health \
  -H "Authorization: Bearer devtoken" | jq .
```

**Response when healthy:**
```json
{
  "senzing_sdk_installed": true,
  "license_configured": true,
  "license_path": "/app/secrets/senzing/g2.lic",
  "grpc_url": "senzing-grpc:8261",
  "client_initialized": true,
  "client_available": true,
  "connection_status": "healthy",
  "errors": [],
  "database_info": {
    "record_count": 17,
    "entity_count": 2
  },
  "overall_status": "healthy"
}
```

---

## Status Meanings

### ✅ **healthy**
All systems working:
- License file found
- Senzing gRPC server connected
- Can communicate with Senzing database
- Ready to resolve entities

### ⚠️ **degraded**
Partially working:
- License found
- Client initialized
- But some features may not work
- Check `errors` array for details

### ❌ **unhealthy**
Not working:
- License missing or invalid
- gRPC server not reachable
- Client failed to initialize
- Cannot perform entity resolution

---

## Troubleshooting

### Problem: "License not configured"

**Check if license exists:**
```bash
ls -lh api/secrets/senzing/g2.lic
```

**Solutions:**
1. Copy your license file to `api/secrets/senzing/g2.lic`
2. Or place base64-encoded license in `api/g2license_*/g2.lic_base64`
3. Restart API: `docker compose restart api`

### Problem: "Senzing client not initialized"

**Check gRPC server:**
```bash
docker compose ps senzing-grpc
```

**Should show:**
```
senzing-grpc   Up X minutes   0.0.0.0:8261->8261/tcp
```

**If not running:**
```bash
# Check logs
docker compose logs senzing-grpc --tail=50

# Restart
docker compose restart senzing-grpc senzing-postgres
docker compose restart api
```

### Problem: "Senzing SDK not installed"

**Rebuild API container:**
```bash
docker compose build api
docker compose up -d api
```

**Verify senzing-grpc package installed:**
```bash
docker compose exec api pip list | grep senzing
```

**Should show:**
```
senzing                   4.0.4
senzing-grpc              0.5.13
```

### Problem: "Connection refused"

**Check environment variable:**
```bash
docker compose exec api env | grep SENZING_GRPC_URL
```

**Should show:**
```
SENZING_GRPC_URL=senzing-grpc:8261
```

**If missing, check docker-compose.yml:**
```yaml
api:
  environment:
    SENZING_GRPC_URL: senzing-grpc:8261
```

---

## Manual Verification

### 1. Check License File

```bash
# Should exist and be binary
file api/secrets/senzing/g2.lic

# Should output:
# api/secrets/senzing/g2.lic: data
```

### 2. Check Services Running

```bash
docker compose ps
```

**Required services:**
- ✅ api (healthy)
- ✅ neo4j (healthy)
- ✅ senzing-postgres (healthy)
- ✅ senzing-grpc (running)
- ✅ senzing-init (exited 0 - one-time init)

### 3. Check Senzing gRPC Server Logs

```bash
docker compose logs senzing-grpc --tail=20
```

**Should see:**
```
Server listening at [::]:8261
```

### 4. Check PostgreSQL Connection

```bash
docker compose exec senzing-postgres psql -U senzing -d senzing -c "\dt"
```

**Should show Senzing tables:**
```
lib_feat, dsrc_record, obs_ent, res_ent, etc.
```

### 5. Test Entity Resolution

```bash
curl -X POST http://localhost:8000/api/entity-resolution/run \
  -H "Authorization: Bearer devtoken" \
  -H "Content-Type: application/json" \
  -d '{"selectedNodeTypes": ["j:CrashDriver"]}' | jq .
```

**Should return:**
```json
{
  "status": "success",
  "resolutionMethod": "senzing",
  ...
}
```

**If `resolutionMethod: "text_based"`** → Senzing isn't working, using fallback

---

## Quick Status Summary

**One-liner to check everything:**
```bash
./check_senzing.sh && echo "✅ All systems GO!" || echo "❌ Issues detected"
```

**Or via API:**
```bash
curl -s http://localhost:8000/api/entity-resolution/health \
  -H "Authorization: Bearer devtoken" | jq '.overall_status'
```

---

## Debug Logging

**Watch Senzing resolution in real-time:**
```bash
./view_senzing_debug.sh
```

Then in another terminal:
```bash
curl -X POST http://localhost:8000/api/entity-resolution/run \
  -H "Authorization: Bearer devtoken" \
  -H "Content-Type: application/json" \
  -d '{"selectedNodeTypes": ["j:CrashDriver"]}'
```

**You should see:**
```
[SENZING_DEBUG] Processing entity: neo4j_id=...
[SENZING_DEBUG]   Mapped: nc_PersonGivenName → PRIMARY_NAME_FIRST = 'Peter'
[SENZING_DEBUG] Senzing response for record_id=...
[SENZING_DEBUG] ✓ DUPLICATE FOUND: Records [...] resolve to ENTITY_ID=2
```

---

## Support

If issues persist:
1. Check `./check_senzing.sh` output
2. Review `errors` array in health response
3. Check Docker logs: `docker compose logs senzing-grpc senzing-postgres api`
4. Verify license hasn't expired (check license file content)
5. Ensure all services are running: `docker compose ps`
