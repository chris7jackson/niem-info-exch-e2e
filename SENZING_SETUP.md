# Senzing Setup Guide

## Current Status
✗ **Using Mock Resolution** - Senzing license not detected

## To Enable Senzing ML-Based Entity Resolution

### Step 1: Obtain a Senzing License
- Request a license from [Senzing.com](https://senzing.com)
- You'll receive a `g2.lic` file

### Step 2: Install the License

#### Method A: Direct File Placement (Recommended)
```bash
# Copy your license file to the secrets directory
cp /path/to/your/g2.lic api/secrets/senzing/g2.lic

# Restart the API container to load the license
docker-compose restart api
```

#### Method B: Environment Variable (Base64)
```bash
# Encode your license file
base64 < /path/to/your/g2.lic > license.txt

# Add to .env file
echo "SENZING_LICENSE_BASE64=$(cat license.txt)" >> .env

# Restart services
docker-compose down
docker-compose up -d
```

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
- Check file permissions: `ls -la api/secrets/senzing/`
- Verify file exists: `file api/secrets/senzing/g2.lic`
- Check API logs: `docker-compose logs api | grep -i senzing`

### Senzing SDK Not Found
- In Docker: Should be installed automatically
- Local dev: Run `pip install senzing`

### Database Errors
- SQLite: Check write permissions on `/data/senzing`
- PostgreSQL: Verify connection string and credentials

## Next Steps

After enabling Senzing:
1. Re-run entity resolution on your crash driver data
2. Compare results between mock and Senzing modes
3. Tune field mappings in `api/config/niem_senzing_mappings.yaml`
4. Adjust confidence thresholds as needed