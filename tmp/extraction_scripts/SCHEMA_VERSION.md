# MRT Enrichment Data Schema Documentation
**Version**: 1.0  
**Last Updated**: 2026-02-02  
**Author**: Enrichment Extraction System

## Overview

This document defines the standardized schema for MRT station enrichment data. All batch extraction files must conform to this schema for successful merging.

---

## Primary Key

**Station Code** is the primary identifier for matching across data sources.
- Format: Line prefix + number (e.g., NS13, CC10, DT11)
- Always use uppercase
- Never use leading zeros (NS1 not NS01)

---

## Station Object Schema

```json
{
  "official_name": "STATION NAME MRT STATION",
  "station_code": "NS13",
  "lines": ["NSL", "DTL"],
  "exits": [
    {
      "exit_code": "A",
      "platforms": [
        {
          "platform_code": "A",
          "towards_code": "NS1",
          "line_code": "NS"
        }
      ],
      "accessibility": ["lift", "escalator", "wheelchair_accessible"],
      "bus_stops": [
        {
          "code": "59009",
          "services": ["39", "85", "103"]
        }
      ],
      "nearby_landmarks": ["Northpoint City", "Yishun Bus Interchange"]
    }
  ],
  "accessibility_notes": ["All exits barrier-free", "Yishun Bus Interchange at Exit E"],
  "last_updated": "2026-02-02T10:00:00",
  "source_url": "https://singapore-mrt-lines.fandom.com/wiki/Station_Name_MRT_Station",
  "extraction_confidence": "high"
}
```

### Field Definitions

#### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `official_name` | string | Station name in ALL CAPS with "MRT STATION" suffix | "YISHUN MRT STATION" |
| `station_code` | string | Primary station code | "NS13" |
| `lines` | array | Array of line codes | ["NSL", "DTL"] |
| `exits` | array | Array of exit objects | See Exit Schema below |
| `accessibility_notes` | array | Special accessibility notes | ["Exit C stairs-only"] |
| `last_updated` | ISO8601 | Timestamp of last extraction | "2026-02-02T10:00:00" |
| `source_url` | string | URL of source page | Fandom wiki URL |
| `extraction_confidence` | enum | "high", "medium", or "low" | "high" |

#### Exit Schema

```json
{
  "exit_code": "A",
  "platforms": [
    {
      "platform_code": "A",
      "towards_code": "NS1",
      "line_code": "NS"
    }
  ],
  "accessibility": ["lift", "escalator", "wheelchair_accessible"],
  "bus_stops": [
    {
      "code": "59009",
      "services": ["39", "85"]
    }
  ],
  "nearby_landmarks": ["Landmark Name"]
}
```

##### Exit Fields

| Field | Type | Description | Values |
|-------|------|-------------|--------|
| `exit_code` | string | Exit identifier | "A", "B", "1", "2" |
| `platforms` | array | Platforms accessible from this exit | See Platform Schema |
| `accessibility` | array | Accessibility features | See Accessibility Values |
| `bus_stops` | array | Bus stops near this exit | See Bus Stop Schema |
| `nearby_landmarks` | array | Major landmarks near exit | ["Mall Name", "Building"] |

##### Platform Schema

```json
{
  "platform_code": "A",
  "towards_code": "NS1",
  "line_code": "NS"
}
```

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `platform_code` | string | Platform letter | "A", "B" |
| `towards_code` | string | **Station code** of destination (NOT name) | "NS1" (not "Jurong East") |
| `line_code` | string | Line code (without "L") | "NS", "EW", "CC", "DT", "NE", "TE", "BP" |

##### Bus Stop Schema

```json
{
  "code": "59009",
  "services": ["39", "85", "103"]
}
```

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `code` | string | 5-digit bus stop code | "59009" |
| `services` | array | Bus service numbers | ["39", "85"] |

##### Accessibility Values

Allowed values in `accessibility` array:

| Value | Meaning |
|-------|---------|
| `wheelchair_accessible` | General wheelchair accessibility |
| `barrier_free` | No barriers/steps at all |
| `lift` | Lift/elevator available |
| `escalator` | Escalator available |
| `stairs_only` | Stairs only - NOT accessible |
| `tactile_guidance` | Tactile paving |
| `accessible_toilet` | Accessible toilet nearby |

---

## Line Code Reference

| Code | Full Name | Example Station |
|------|-----------|----------------|
| NS | North-South Line | NS13 (Yishun) |
| EW | East-West Line | EW1 (Pasir Ris) |
| CC | Circle Line | CC10 (MacPherson) |
| DT | Downtown Line | DT11 (Newton) |
| NE | North-East Line | NE14 (Hougang) |
| TE | Thomson-East Coast Line | TE7 (Bright Hill) |
| BP | Bukit Panjang LRT | BP6 (Bukit Panjang) |
| SE | Sengkang LRT | SE1 (Sengkang) |
| PE | Punggol LRT | PE1 (Punggol) |

---

## Schema Evolution

### Version 1.0 (2026-02-02)
- Initial schema definition
- Standardized on station codes for `towards_code`
- Added `nearby_landmarks` field
- Standardized accessibility values

---

## Validation Rules

1. **station_code** must match pattern: ^[A-Z]{2}\d{1,2}$
2. **towards_code** must be a valid station code
3. **exit_code** should be uppercase letter or number
4. **bus_stop.code** must be exactly 5 digits
5. **extraction_confidence** must be one of: "high", "medium", "low"
6. **lines** array must contain valid line abbreviations (NSL, EWL, CCL, DTL, NEL, TEL, BPL, SKL, PGL)

---

## Matching Rules for Cross-Reference

When matching enrichment data to the main transit graph:

1. **Primary Key**: Use `station_code` from enrichment data
2. **Fuzzy Matching**: If no exact match, try:
   - Normalize station names (remove "MRT", "LRT", "Station")
   - Case-insensitive match
   - Remove special characters
3. **Multiple Codes**: Interchange stations have multiple codes (e.g., NS21 + DT11 = Newton)
   - Match on ANY of the codes
   - Merge data if multiple sources found
