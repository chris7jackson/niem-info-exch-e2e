# Senzing License Setup - Quick Start

Simple 2-step process to add your Senzing license.

## Quick Setup

### Step 1: Get Your License

Contact support@senzing.com to obtain your license. You'll receive a zip file like:
```
g2license_20251201-120000.zip
```

### Step 2: Unzip Into Project

```bash
unzip g2license_20251201-120000.zip -d api/
```

This creates:
```
api/g2license_20251201-120000/
  └── g2.lic_base64
```

### Step 3: Start the System

```bash
docker compose up -d
```

**That's it!** The license automatically:
- Decodes from base64 → binary format
- Saves to `api/secrets/senzing/g2.lic`
- Becomes available to all Senzing services (API, gRPC, init)

## Verify Setup

Run the diagnostic script:
```bash
./check_senzing.sh
```

**Expected output:**
```
✅ Senzing Status: HEALTHY

Component Status:
┌─────────────────────────────────────────────┐
│ ✅ Senzing SDK          : healthy
│ ✅ License File         : valid (binary (valid format))
│ ✅ gRPC Server          : healthy (senzing-grpc:8261)
│ ✅ PostgreSQL Database  : healthy
└─────────────────────────────────────────────┘
```

Or check via API:
```bash
curl http://localhost:8000/api/entity-resolution/health \
  -H "Authorization: Bearer devtoken" | jq '.overall_status'
```

Should return: `"healthy"`

## Troubleshooting

### License Not Found

**Check if folder exists:**
```bash
ls -la api/g2license_*
```

**Should show:**
```
drwxr-xr-x  g2license_20251201-120000/
```

**If missing:**
- Re-extract the zip file into `api/` directory
- Make sure you extracted TO `api/`, not FROM `api/`

### License Not Decoded

**Check logs:**
```bash
docker compose logs api | grep -i "senzing license"
```

**Should show:**
```
✅ Senzing license found at /app/secrets/senzing/g2.lic
✅ Senzing license decoded successfully
```

**If shows "License file not found":**
- Restart API to trigger auto-decode: `docker compose restart api`
- Wait 10 seconds and check again

### License Invalid

**Verify license file format:**
```bash
file api/secrets/senzing/g2.lic
```

**Should show:**
```
api/secrets/senzing/g2.lic: data
```

**If shows "ASCII text":**
- The base64 decode failed
- Check the original `g2.lic_base64` file exists
- Verify it contains base64-encoded data (not plain text)

## Security

### License Files Are Protected

All license files are automatically excluded from git:
- ✅ `api/secrets/` - gitignored
- ✅ `api/g2license_*/` - gitignored
- ✅ `*.lic` - gitignored
- ✅ `*.lic_base64` - gitignored

**You cannot accidentally commit your license** - it's safe!

### Never Commit License

The license is sensitive and tied to your organization. It should NEVER be:
- ❌ Committed to git
- ❌ Shared publicly
- ❌ Embedded in code
- ❌ Added to .env (if .env is committed)

Our setup ensures this by:
- Using auto-decode from gitignored folder
- Storing decoded license in gitignored secrets/
- No license data in environment files

## Production Deployment

For production, consider:

1. **Use secrets management** (Kubernetes secrets, AWS Secrets Manager, etc.)
2. **Mount license as Docker secret**:
   ```yaml
   secrets:
     senzing_license:
       file: ./api/secrets/senzing/g2.lic
   ```
3. **Set up license rotation** when license expires
4. **Monitor license expiration** via health endpoint

## FAQ

**Q: Do I need to set SENZING_LICENSE_BASE64 environment variable?**
A: No! That's the old method. Just unzip the folder and you're done.

**Q: Where is the license stored?**
A: Auto-decoded to `api/secrets/senzing/g2.lic` (gitignored)

**Q: How do I update my license?**
A: Unzip new license folder, delete old one, restart: `docker compose restart api senzing-grpc`

**Q: Can I delete the g2license_* folder after setup?**
A: Yes, once the license is decoded to `api/secrets/senzing/g2.lic`, you can delete the folder. But keeping it allows easy re-initialization.

**Q: What if my license expires?**
A: Get new license from Senzing, unzip to `api/`, restart services. The health check will show "invalid" when expired.

## Summary

**Before:** 5 steps, manual base64 encoding, dual configuration
**After:** 2 steps (unzip, start), fully automatic

```bash
# Complete setup in 2 commands:
unzip g2license_*.zip -d api/
docker compose up -d
```

Check status anytime: `./check_senzing.sh`
