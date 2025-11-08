# Senzing Match Details Feature

## Overview

The Senzing Match Details feature provides transparency into how entity resolution was performed by displaying detailed information about how Senzing matched entities together. This information is displayed in the UI after running entity resolution with the Senzing SDK.

## Features

### 1. Match Quality Distribution
Shows how confident Senzing is about each entity match, categorized into three levels:

- **High Confidence**: Strong evidence that entities are the same (MATCH_LEVEL >= 3 or MATCH_LEVEL_CODE in ['RESOLVED', 'EXACT_MATCH'])
- **Medium Confidence**: Probable matches (MATCH_LEVEL >= 2 or MATCH_LEVEL_CODE in ['POSSIBLY_SAME', 'POSSIBLY_RELATED'])
- **Low Confidence**: Weak matches (MATCH_LEVEL < 2)

**Note**: This counts individual record-level matches, not entity groups.

### 2. How Entities Were Matched
Displays which combinations of attributes Senzing used to determine entities are the same.

**Examples**:
- `+NAME+DOB` → "Name + Date of Birth"
- `Exactly_same` → "Exact match (all attributes identical)"
- `+NAME+ADDRESS+PHONE` → "Name + Address + Phone"

The count shows how many times each combination was used across all matches.

### 3. Attributes Used (Optional)
Shows which types of attributes were found in matched entities with quality scores.

**Score Calculation**:
Progress bars are calculated using one of three methods (in order of preference):

1. **Direct Feature Scores** (if available from Senzing):
   - Uses `FEAT_SCORE` values (0-100) from Senzing's ML algorithms
   - Example: "John Smith" vs "J. Smith" might score 85/100

2. **USAGE_TYPE Mapping** (fallback):
   - `FF` (Full Feature) = 100 - Exact match
   - `FM/FME` (Feature Match) = 75 - Close match
   - `FNF` (Feature Not Found) = 50 - Partial match

3. **Feature Presence Count** (fallback):
   - Score = (number of feature values / number of records) × 100
   - Example: If 5 out of 5 records have NAME, score = 100%

**Display Logic**:
- Only shows attributes with scores > 0
- If all scores are 0, the entire section is hidden
- Average score is calculated across all matched records and rounded to 2 decimal places

### 4. Senzing Rules Used
Shows which Senzing resolution rules were applied during entity matching.

Each rule defines specific criteria for when entities should be considered the same. The count shows how many times each rule was triggered.

**Example**:
```
CNAME_CFF_CSTAB        15 times
SAME_ID                 8 times
```

## Implementation Details

### Backend Changes

#### 1. Senzing Client (`api/src/niem_api/clients/senzing_client.py`)

Enhanced the Senzing client to request additional match details:

```python
flags = flags or (
    SzEngineFlags.SZ_ENTITY_DEFAULT_FLAGS |
    SzEngineFlags.SZ_INCLUDE_FEATURE_SCORES |
    SzEngineFlags.SZ_INCLUDE_MATCH_KEY_DETAILS |
    SzEngineFlags.SZ_ENTITY_INCLUDE_RECORD_MATCHING_INFO
)
```

**Flags Explained**:
- `SZ_ENTITY_DEFAULT_FLAGS`: Base entity information
- `SZ_INCLUDE_FEATURE_SCORES`: Feature score details in responses
- `SZ_INCLUDE_MATCH_KEY_DETAILS`: Detailed matching key information
- `SZ_ENTITY_INCLUDE_RECORD_MATCHING_INFO`: Record-level matching details

#### 2. Match Details Extraction (`api/src/niem_api/handlers/entity_resolution.py`)

**Function**: `_extract_match_details_from_senzing_results(resolved_entities: Dict) -> Dict`

**Input Structure**:
```python
resolved_entities = {
    senzing_entity_id: {
        'entities': [...],  # List of matched entities
        'senzing_data': {   # Senzing response for this entity
            'ENTITY_ID': int,
            'ENTITY_NAME': str,
            'RECORDS': [
                {
                    'MATCH_KEY': str,
                    'MATCH_LEVEL': int,
                    'MATCH_LEVEL_CODE': str,
                    'ERRULE_CODE': str,
                    'FEATURES': {...}  # Optional
                }
            ],
            'FEATURES': {...}  # Entity-level features
        }
    }
}
```

**Output Structure**:
```python
{
    'totalEntitiesMatched': int,
    'totalResolvedGroups': int,
    'matchQualityDistribution': {
        'high': int,
        'medium': int,
        'low': int
    },
    'commonMatchKeys': {
        'match_key_string': count
    },
    'featureScores': {
        'FEATURE_TYPE': {
            'total': float,
            'count': int,
            'average': float
        }
    },
    'resolutionRules': {
        'rule_code': count
    }
}
```

**Aggregation Logic**:
- Iterates through all resolved entity groups
- Only processes groups with 2+ entities (duplicates)
- Extracts data from each record in the group
- Calculates averages and sorts by frequency
- Returns top 10 match keys and resolution rules

#### 3. API Response (`api/src/niem_api/handlers/entity_resolution.py`)

Modified the entity resolution response to include match details:

```python
response = {
    'status': 'success',
    'message': str,
    'entitiesExtracted': int,
    'duplicateGroupsFound': int,
    'resolvedEntitiesCreated': int,
    'relationshipsCreated': int,
    'entitiesResolved': int,
    'resolutionMethod': str,
    'nodeTypesProcessed': list,
    'matchDetails': dict  # NEW - Only included if using Senzing
}
```

### Frontend Changes

#### 1. TypeScript Interface (`ui/src/lib/api.ts`)

Added new interfaces:

```typescript
export interface MatchDetails {
  totalEntitiesMatched: number;
  totalResolvedGroups: number;
  matchQualityDistribution: {
    high: number;
    medium: number;
    low: number;
  };
  commonMatchKeys: Record<string, number>;
  featureScores: Record<string, {
    total: number;
    count: number;
    average: number;
  }>;
  resolutionRules: Record<string, number>;
}

export interface EntityResolutionResponse {
  // ... existing fields ...
  matchDetails?: MatchDetails;
}
```

#### 2. UI Component (`ui/src/components/EntityResolutionPanel.tsx`)

**New Components**:
- `Tooltip`: Reusable component for displaying helpful information on hover
- Match Details expandable section (only shown when using Senzing)

**Helper Functions**:
- `formatMatchKey(matchKey: string)`: Converts Senzing match keys to human-readable format
  - `"Exactly_same"` → `"Exact match (all attributes identical)"`
  - `"+NAME+DOB"` → `"Name + Date of Birth"`
  - `"Record_Type"` → `"Record Type"`

**State Management**:
```typescript
const [showMatchDetails, setShowMatchDetails] = useState(false);
```

**Display Logic**:
```typescript
{lastResult.matchDetails && lastResult.resolutionMethod === 'senzing' && (
  // Match details section
)}
```

## User Interface

### Expandable Section
Click "Match Details" to expand/collapse the detailed information.

### Visual Elements
- **Info Icons**: Hover to see explanatory tooltips
- **Progress Bars**: Visual representation of attribute scores (0-100%)
- **Color Coding**:
  - High confidence: Green
  - Medium confidence: Yellow
  - Low confidence: Orange
- **Counts**: Grammatically correct singular/plural ("1 time" vs "5 times")

### Tooltips
Each section has a hover tooltip explaining what the metric means:

```
Match Quality Distribution:
"Shows how confident Senzing is about each entity match. High confidence
means strong evidence that entities are the same person/organization.
This counts individual record-level matches, not entity groups."

How Entities Were Matched:
"Shows which combinations of attributes Senzing used to determine entities
are the same. For example, 'Name + Date of Birth' means Senzing matched
entities that had the same name AND date of birth. The count shows how
many times each combination was used."

Attributes Used:
"Shows which types of attributes were found in the matched entities.
A score of 100 means the attribute was present in all matched records.
Lower scores indicate the attribute was found in some but not all records,
or match quality varies."

Senzing Rules Used:
"Shows which Senzing resolution rules were applied during entity matching.
Each rule defines specific criteria for when entities should be considered
the same. The count shows how many times each rule was triggered."
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Senzing Client (with enhanced flags)                        │
│    - Requests: FEATURE_SCORES, MATCH_KEY_DETAILS, etc.         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Senzing SDK Response                                         │
│    - ENTITY_ID, ENTITY_NAME                                     │
│    - RECORDS[].MATCH_KEY, MATCH_LEVEL, ERRULE_CODE             │
│    - FEATURES{} (entity-level or record-level)                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. _extract_match_details_from_senzing_results()               │
│    - Aggregates data from all resolved entities                │
│    - Calculates averages and distributions                     │
│    - Sorts by frequency                                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. API Response                                                 │
│    - Includes matchDetails field (if Senzing used)             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. EntityResolutionPanel Component                             │
│    - Displays expandable match details section                 │
│    - Formats keys, shows tooltips, renders progress bars       │
└─────────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### No Match Details Displayed

**Possible Causes**:
1. **Using text-based resolution**: Match details only available with Senzing SDK
2. **No duplicates found**: Match details only generated when entities are matched

**Check**:
- Verify `resolutionMethod === 'senzing'` in the response
- Check that `duplicateGroupsFound > 0`

### Feature Scores All Zero

**Possible Causes**:
1. Senzing response doesn't include score metadata
2. Enhanced flags not returning expected data structure
3. Features exist but without scoring information

**Behavior**:
- The "Attributes Used" section will be completely hidden
- Other sections (Match Quality, Match Keys, Rules) will still display

**To Enable Scores**:
- Ensure Senzing SDK is properly licensed
- Verify enhanced flags are set in `senzing_client.py`
- Check Senzing documentation for your version's feature score availability

### Match Keys Show Technical Names

**Expected Behavior**:
- `formatMatchKey()` function converts technical keys to readable format
- If a key is not recognized, it will be title-cased and underscores replaced with spaces

**Add New Mappings**:
Edit `formatMatchKey()` in `EntityResolutionPanel.tsx`:

```typescript
const formatMatchKey = (matchKey: string) => {
  // Add special case handling
  if (matchKey === 'YOUR_KEY') {
    return 'Your Readable Description';
  }

  // ... existing logic
}
```

## Performance Considerations

### Backend
- Match details extraction runs once per entity resolution operation
- Aggregation is O(n*m) where n = number of entity groups, m = average records per group
- Top 10 limiting prevents excessive data transfer

### Frontend
- Match details are hidden by default (expandable)
- Only renders sections with data
- Tooltips are lazy-rendered on hover

## Future Enhancements

### Potential Improvements
1. **Record-level details**: Show individual record matches instead of aggregates
2. **Export functionality**: Download match details as CSV/JSON
3. **Visualization**: Charts for match quality distribution
4. **Filtering**: Filter by confidence level or match key
5. **Comparison**: Side-by-side comparison of matched entities
6. **Historical tracking**: Track match details across multiple resolution runs

### Additional Senzing Flags to Explore
- `SZ_ENTITY_INCLUDE_RECORD_FEATURE_STATS`: Feature statistics at record level
- `SZ_ENTITY_INCLUDE_REPRESENTATIVE_FEATURES`: Representative feature examples
- `SZ_INCLUDE_INTERNAL_FEATURES`: Internal Senzing features
- `SZ_ENTITY_INCLUDE_FEATURE_ELEMENTS`: Individual feature elements

## References

- Senzing SDK Documentation: https://senzing.zendesk.com/hc/en-us/categories/360000120514-Senzing-API
- Senzing Python SDK: https://github.com/senzing-garage/sz-sdk-python
- NIEM Specification: https://niem.github.io/

## Version History

- **v1.0** (2025-01-07): Initial implementation
  - Match quality distribution
  - Common match keys with formatting
  - Feature scores with progress bars
  - Resolution rules display
  - Tooltip component for explanations
  - Centered tooltip positioning
  - Smart display logic (hide sections with no data)
