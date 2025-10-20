# Troubleshooting CMF Tool Issues

## Overview

The CMF (Common Model Format) tool is used to convert NIEM XSD schemas to CMF format and JSON Schema. When it fails, the API returns a `400 Bad Request` status with detailed error information.

## Important: 400 Errors Are Not Always Bugs

A `400 Bad Request` response is the **intended behavior** when:
- ✅ Schema has validation errors (NIEM NDR violations)
- ✅ Required schema dependencies are missing
- ✅ CMF tool execution fails

**The 400 status means "check the error details"** - it could be a legitimate validation issue or a tool execution problem.

## Common Issues After Docker OS Abstraction Fix

### Issue: CMF Tool Execution Fails After Code Changes

**Symptoms:**
- API returns `400 Bad Request`
- Error message: "CMF tool is not available" or "CMF tool execution failed"
- Previously working schemas now fail to upload

**Root Cause:**
The recent fix to remove Windows platform detection and add `chmod +x` in the Dockerfile requires **rebuilding the container** to take effect. The changes are in the Dockerfile, not the Python code, so a simple restart won't apply them.

**Solution:**
```bash
# Stop and remove containers
docker compose down

# Rebuild and restart
docker compose up -d --build

# Verify the fix worked
./diagnose-cmf.sh      # On Linux/Mac
.\diagnose-cmf.ps1     # On Windows PowerShell
```

### How to Verify the Fix

After rebuilding, the diagnostic scripts will check:

1. ✅ CMF tool file exists: `/app/third_party/niem-cmf/cmftool-1.0/bin/cmftool`
2. ✅ File has executable permissions (should show `-rwxr-xr-x`)
3. ✅ Java is installed (OpenJDK 21)
4. ✅ CMF tool executes: `cmftool version` returns version string

## Using the Diagnostic Scripts

### On Windows (PowerShell)
```powershell
.\diagnose-cmf.ps1
```

### On Linux/Mac (Bash)
```bash
./diagnose-cmf.sh
```

These scripts will:
- Check if Docker and the API container are running
- Verify CMF tool file exists and has correct permissions
- Test Java installation
- Try executing the CMF tool
- Show recent error logs
- Provide specific next steps based on findings

## Understanding 400 Error Responses

When you get a `400 Bad Request`, check the response body for details:

### 1. Tool Execution Error
```json
{
  "message": "Schema upload failed: CMF tool is not available on this server",
  "cmf_error": "CMF tool not available"
}
```
**Fix:** Container needs rebuilding (see above)

### 2. Legitimate Validation Error
```json
{
  "message": "Schema upload rejected: NIEM NDR validation found 5 error(s)",
  "scheval_report": {
    "status": "fail",
    "errors": [
      {
        "file": "schema.xsd",
        "line": 42,
        "message": "Element must have documentation",
        "severity": "error"
      }
    ]
  }
}
```
**Fix:** Correct the schema validation errors

### 3. Missing Dependencies Error
```json
{
  "message": "Schema upload rejected: Missing 3 required schema dependencies",
  "import_validation_report": {
    "status": "fail",
    "missing_count": 3,
    "files": [...]
  }
}
```
**Fix:** Upload all required schema files together

## Manual Container Verification

If the diagnostic scripts aren't working, you can manually verify:

```bash
# Get API container ID
docker compose ps

# Check file permissions inside container
docker exec -it <container-id> ls -la /app/third_party/niem-cmf/cmftool-1.0/bin/

# Expected output should show execute permissions:
# -rwxr-xr-x 1 appuser appgroup 9286 Oct 20 12:25 cmftool

# Test Java
docker exec -it <container-id> java -version

# Test CMF tool
docker exec -it <container-id> /app/third_party/niem-cmf/cmftool-1.0/bin/cmftool version
```

## What Changed: Docker OS Abstraction Fix

**Problem:** The code was checking `platform.system()` inside the container to decide between `.bat` (Windows) and shell script (Unix). But `platform.system()` always returns "Linux" inside a Docker container, regardless of the host OS.

**Solution:**
1. Removed platform detection from Python code - always use shell scripts
2. Added `chmod +x` in Dockerfile to ensure scripts are executable
3. Container now works identically on Windows, Mac, and Linux hosts

## Still Having Issues?

If the diagnostic script shows everything is working but you're still getting 400 errors:

1. **Check the actual error message** in the 400 response body
2. **Look at the full API logs:**
   ```bash
   docker compose logs api --tail=200 > full-logs.txt
   ```
3. **Try the sample schemas** to verify the tool works:
   ```bash
   # The CrashDriver sample should upload successfully (with Skip NDR checked)
   samples/CrashDriver-cmf/CrashDriverSchemaSet/
   ```
4. **Check if it's a schema-specific issue** - try a minimal valid schema

## Related Files

- `/api/Dockerfile` - Contains `chmod +x` commands for tool scripts
- `/api/src/niem_api/clients/cmf_client.py` - CMF tool client (platform detection removed)
- `/api/src/niem_api/services/cmf_tool.py` - CMF business logic
- `/api/src/niem_api/handlers/schema.py` - Schema upload handler (returns 400 on failures)
