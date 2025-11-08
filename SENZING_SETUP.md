# Senzing Setup Guide

## Current Status
✗ **Using Mock Resolution** - Senzing license not detected

## To Enable Senzing ML-Based Entity Resolution

### Step 1: Obtain a Senzing License
- Contact support@senzing.com to request a license
- You'll receive a zip file (e.g., `g2license_20251201-120000.zip`)
- This zip contains a folder with a base64-encoded license file

### Step 2: Install the License

#### Method A: License Folder Auto-Detection (Recommended - Easiest!)

This is the **recommended method** - the system automatically detects and decodes your license!

```bash
# 1. Unzip your license folder into the api/ directory
unzip g2license_20251201-120000.zip -d api/

# 2. Verify the structure matches what the system expects
ls api/g2license_20251201-120000/g2.lic_base64
# Should show: api/g2license_20251201-120000/g2.lic_base64

# 3. Restart the API container to load the license
docker compose restart api

# 4. Check logs to confirm license was decoded
docker compose logs api | grep -i senzing
# Should show: "✅ Senzing license decoded successfully"
```

**What the system expects:**
- **Folder name pattern**: `g2license_*` (e.g., `g2license_20251201-120000`)
- **File inside folder**: `g2.lic_base64` (base64-encoded license)
- **Location**: `api/g2license_*/g2.lic_base64`

The system automatically:
1. Searches for `g2license_*` folders in `api/` directory on startup
2. Finds the `*.lic_base64` file inside
3. Decodes it and saves to `api/secrets/senzing/g2.lic`
4. Initializes Senzing with the decoded license

**Note**: If you have multiple license folders, the system uses the most recent one (sorted by folder name).

#### Method B: Direct File Placement (Advanced Users)

If you already have a decoded `g2.lic` file (not base64-encoded):

```bash
# Copy your decoded license file to the secrets directory
mkdir -p api/secrets/senzing
cp /path/to/your/g2.lic api/secrets/senzing/g2.lic

# Restart the API container to load the license
docker compose restart api
```

#### Method C: Environment Variable (For Docker Services Only)

This method is for configuring the `senzing-grpc` and `senzing-init` Docker services, not the main API:

```bash
# Encode your license file
base64 < /path/to/your/g2.lic > license_base64.txt

# Add to .env file
echo "SENZING_LICENSE_BASE64=$(cat license_base64.txt)" >> .env

# Restart services
docker compose down
docker compose up -d
```

**Note**: The API service uses Method A (g2license_* folder), not this environment variable.

### Step 3: Install Senzing Python SDK (if running locally)
```bash
# For local development (not needed in Docker)
pip install senzing
```

### Step 4: Verify Senzing is Active
After restarting, check the entity resolution status:
```bash
curl http://localhost:8000/api/entity-resolution/status \
  -H "Authorization: Bearer devtoken" | jq .
```

You should see:
```json
{
  "senzing_available": true,
  "mode": "senzing",
  "message": "Using Senzing SDK for entity resolution"
}
```

## Testing with Crash Driver Data

Once Senzing is enabled:

1. **Upload your crash driver XML files** (if not already done)
2. **Run entity resolution** with Senzing:
   - Go to http://localhost:3000/graph
   - Click "Entity Resolution"
   - Select node types (e.g., `j:CrashDriverType`)
   - Click "Run Entity Resolution"
   - You'll see "Method: Senzing SDK" instead of "Mock"

## Senzing vs Mock Resolution

### Mock Resolution (Current)
- Simple name matching
- Case-insensitive comparison
- Basic punctuation normalization
- No ML features

### Senzing SDK (With License)
- Machine learning-based matching
- Fuzzy name matching
- Phonetic matching
- Address standardization
- Date normalization
- Relationship analysis
- Confidence scoring

## Database Configuration

Senzing uses SQLite by default. For production, configure PostgreSQL:

```bash
# In .env file
SENZING_DATABASE_URL=postgresql://user:password@host:5432/senzing_db
```

## Troubleshooting

### License Not Detected

**If using Method A (g2license_* folder):**
```bash
# 1. Check if the license folder exists and has correct structure
ls -la api/g2license_*/
# Should show a folder with g2.lic_base64 file inside

# 2. Check if the file has correct naming pattern
ls api/g2license_*/g2.lic_base64
# Should show the base64 encoded license file

# 3. Check API logs for license detection
docker compose logs api | grep -i license
# Look for: "Searching for Senzing license in..." and "✅ Senzing license decoded successfully"

# 4. Verify decoded license was created
ls -la api/secrets/senzing/g2.lic
# Should show the decoded license file (created automatically)

# 5. Check folder permissions (must be readable by Docker)
chmod -R 755 api/g2license_*/
```

**If the license folder pattern doesn't match:**
- Ensure folder name starts with `g2license_`
- License file inside must be named `g2.lic_base64` or end with `.lic_base64`
- If you have a different structure, use Method B (direct file placement) instead

**If using Method B (direct file placement):**
```bash
# Check file permissions
ls -la api/secrets/senzing/
# g2.lic should exist and be readable

# Verify file is a valid license (not base64)
file api/secrets/senzing/g2.lic
# Should NOT say "ASCII text" (that would be base64-encoded)
```

### Senzing SDK Not Found
- In Docker: Should be installed automatically via requirements.txt
- Local dev: Run `pip install senzing-grpc` (for SDK v4 with gRPC)
- Check logs: `docker compose logs api | grep -i "senzing.*import"`

### Database Errors
- **SQLite** (default): Check write permissions on `/data/senzing` volume
- **PostgreSQL** (production): Verify `SENZING_DB_PASSWORD` is set in `.env` and matches docker-compose.yml
- Check connection: `docker compose logs senzing-postgres`

### License File Format Issues
```bash
# If you have a base64-encoded license but not in g2license_* folder:
# Option 1: Create the expected folder structure
mkdir -p api/g2license_manual
cp your-license.lic_base64 api/g2license_manual/g2.lic_base64

# Option 2: Decode it manually and use Method B
base64 -d < your-license.lic_base64 > api/secrets/senzing/g2.lic
```

### Still Not Working?

Check the complete startup sequence:
```bash
# Full API logs
docker compose logs api

# Look for these key messages:
# 1. "Searching for Senzing license in /app/licenses/g2license_*"
# 2. "Found license file: /app/licenses/g2license_.../g2.lic_base64"
# 3. "✅ Senzing license decoded successfully to /app/secrets/senzing/g2.lic"
# 4. "Senzing client initialized successfully"

# If you see errors, they will indicate the specific issue
```

## Next Steps

After enabling Senzing:
1. Re-run entity resolution on your crash driver data
2. Compare results between mock and Senzing modes
3. Tune field mappings in `api/config/niem_senzing_mappings.yaml`
4. Adjust confidence thresholds as needed