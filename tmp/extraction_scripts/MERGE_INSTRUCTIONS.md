# MRT Enrichment Data Merge Instructions

**Document Version**: 1.0  
**Last Updated**: 2026-02-02  
**Purpose**: Guide for combining batch extraction files into the final output

---

## When to Merge

**DO NOT MERGE** until:
1. All batches are complete (or you explicitly give the go-ahead)
2. Schema validation passes for all batch files
3. Station codes are verified against `mrt_transit_graph.json`
4. You've reviewed the data quality

---

## Merge Process

### Step 1: Validate All Batches

```bash
# Check all batch files exist
ls -la tmp/extraction_scripts/batch*.json

# Validate JSON syntax
for file in tmp/extraction_scripts/batch*.json; do
  python3 -c "import json; json.load(open('$file'))" && echo "✓ $file valid"
done
```

### Step 2: Check Schema Compliance

Verify each batch follows `SCHEMA_VERSION.md`:
- All required fields present
- Station codes match pattern [A-Z]{2}\d{1,2}
- `towards_code` uses station codes (not names)
- Bus stop codes are 5 digits

### Step 3: Merge Batches

```bash
# Run the merge script (to be created when you give go-ahead)
python3 merge_enrichment_data.py
```

The merge script will:
1. Load all batch JSON files
2. Combine into single `stations` object
3. Handle duplicate station codes (merge data)
4. Validate against `mrt_transit_graph.json`
5. Output to `output/mrt_enrichment_data.json`

### Step 4: Post-Merge Validation

```bash
# Count stations in output
python3 -c "import json; data = json.load(open('output/mrt_enrichment_data.json')); print(f'Total stations: {len(data[\"stations\"])}')"

# Verify all expected stations present
python3 validate_coverage.py
```

---

## File Structure

```
mrt-data/
├── tmp/extraction_scripts/
│   ├── batch1_enrichment_data.json    # Complete
│   ├── batch2_enrichment_data.json    # Complete
│   ├── batch3_enrichment_data.json    # Pending...
│   └── PROGRESS_REPORT.md             # Live tracker
├── output/
│   ├── mrt_enrichment_data.json       # MERGE TARGET (currently partial)
│   └── mrt_transit_graph.json         # Reference data
├── EXTRACTION_MANIFEST.json           # Batch registry
├── STATION_MASTER_INDEX.json          # Station lookup
├── SCHEMA_VERSION.md                  # This doc
└── MERGE_INSTRUCTIONS.md              # This doc
```

---

## Pre-Merge Checklist

- [ ] All batch files created
- [ ] All batch files valid JSON
- [ ] No duplicate station codes across batches (unless interchange)
- [ ] `EXTRACTION_MANIFEST.json` updated with all batches
- [ ] `STATION_MASTER_INDEX.json` includes all extracted stations
- [ ] `failed_stations.json` reviewed (any critical stations missing?)
- [ ] Schema validation passed for all batches
- [ ] User has given explicit "go-ahead" signal

---

## Merge Conflict Resolution

### Case 1: Same Station in Multiple Batches

**Resolution**: Merge data intelligently
- Concatenate unique `exits`
- Merge `accessibility_notes` arrays
- Keep most recent `last_updated` timestamp
- Mark `extraction_confidence` as "high" if both sources agree

### Case 2: Different Data for Same Exit

**Resolution**: Prefer more detailed source
- Compare number of fields populated
- Prefer "high" confidence over "medium"
- Log discrepancy for manual review

### Case 3: Interchange Station (Multiple Codes)

**Resolution**: Single entry with all codes
- Example: Newton = NS21 + DT11
- Include both codes in `lines` array
- Merge platform data from both lines

---

## Post-Merge Verification

After merging, verify:

1. **Count Check**: Total stations = 187 (or as extracted)
2. **Code Check**: All station codes match `mrt_transit_graph.json`
3. **Exit Check**: Every station has at least 1 exit
4. **Bus Stop Check**: Bus stop codes are 5-digit numeric
5. **Accessibility Check**: All exits have accessibility array
6. **URL Check**: All `source_url` values are valid URLs

---

## Rollback Plan

If merge fails:

1. Keep backup of original `mrt_enrichment_data.json`
2. Restore from backup: `cp mrt_enrichment_data.json.backup mrt_enrichment_data.json`
3. Fix issues in batch files
4. Re-run merge

---

## Next Steps After Merge

1. Update `output/README.md` with final data summary
2. Archive batch files to `tmp/extraction_scripts/archive/`
3. Clear `EXTRACTION_MANIFEST.json` pending batches
4. Mark project as complete

---

## Contact

For merge issues or questions, refer to:
- `SCHEMA_VERSION.md` - Data format questions
- `STATION_MASTER_INDEX.json` - Station lookup issues
- `EXTRACTION_MANIFEST.json` - Batch status questions
