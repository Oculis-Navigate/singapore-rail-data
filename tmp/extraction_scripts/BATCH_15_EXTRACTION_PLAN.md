# MRT Station Extraction Plan - Major Lines Remaining

## Status Summary
- **Total Stations**: 187
- **Already Extracted**: 121 (64.7% complete)
- **Failed (LRT)**: 41 stations (404 errors)
- **Remaining Major MRT**: 53 stations (28.3%)

## Extraction Batch Plan (Batch 15 Series)

### Batch 15A: North-East Line Completion (11 stations)
**Priority**: HIGH - Complete entire NEL line
**Stations**: NE5, NE7, NE8, NE9, NE10, NE11, NE13, NE14, NE15, NE16, NE18

```
NE5  - Clarke Quay
NE7  - Little India  
NE8  - Farrer Park
NE9  - Boon Keng
NE10 - Potong Pasir
NE11 - Woodleigh
NE13 - Kovan
NE14 - Hougang
NE15 - Buangkok
NE16 - Sengkang
NE18 - Punggol Coast
```

### Batch 15B: Thomson-East Coast Line (12 stations)
**Priority**: HIGH - Complete TEL line
**Stations**: TE1, TE2, TE3, TE4, TE5, TE6, TE7, TE8, TE15, TE16, TE20, TE21

```
TE1  - Woodlands North
TE2  - Woodlands
TE3  - Woodlands South
TE4  - Springleaf
TE5  - Lentor
TE6  - Mayflower
TE7  - Bright Hill
TE8  - Upper Thomson
TE15 - Great World
TE16 - Havelock
TE20 - Marina Bay
TE21 - Marina South
```

### Batch 15C: Downtown Line (22 stations)
**Priority**: MEDIUM - Complete DTL line
**Stations**: DT1, DT2, DT3, DT4, DT5, DT6, DT7, DT8, DT23, DT24, DT25, DT27, DT28, DT29, DT30, DT31, DT32, DT33, DT34, DT35, DT36

```
DT1  - Bukit Panjang
DT2  - Cashew
DT3  - Hillview
DT4  - Hume
DT5  - Beauty World
DT6  - King Albert Park
DT7  - Sixth Avenue
DT8  - Tan Kah Kee
DT23 - Bendemeer
DT24 - Geylang Bahru
DT25 - Mattar
DT27 - Ubi
DT28 - Kaki Bukit
DT29 - Bedok North
DT30 - Bedok Reservoir
DT31 - Tampines West
DT32 - Tampines
DT33 - Tampines East
DT34 - Upper Changi
DT35 - Expo
DT36 - Xilin
```

### Batch 15D: Final MRT Stations (8 stations)
**Priority**: LOW - Complete remaining lines
**Stations**: NS2, NS3, NS4, NS10, NS11, NS22, NS27, EW2

```
NS2  - Bukit Batok
NS3  - Bukit Gombak
NS4  - Choa Chu Kang
NS10 - Admiralty
NS11 - Sembawang
NS22 - Orchard
NS27 - Marina Bay
EW2  - Tampines
```

## Notes for Future Agents

### Data Quality Issues Found
- Many stations I thought were extracted are actually missing
- Transit graph shows 221 total codes (includes interchanges and future lines)
- Focus only on the 53 stations listed above from major operational lines

### Extraction Workflow
1. Always run `python3 validate_batches.py` before starting
2. Use Fandom wiki URLs: `https://singapore-mrt-lines.fandom.com/wiki/{Station_Name}_MRT_Station`
3. Document all failures in `failed_stations.json`
4. Update all tracking files after each batch:
   - `EXTRACTION_MANIFEST.json`
   - `STATION_MASTER_INDEX.json`
   - `PROGRESS_REPORT.md`

### Expected Timeline
- **Batch 15A**: 11 NEL stations (critical - complete the line)
- **Batch 15B**: 12 TEL stations (critical - complete the line)
- **Batch 15C**: 22 DTL stations (large batch, may need splitting)
- **Batch 15D**: 8 remaining stations (final cleanup)

### Success Criteria
After Batch 15 series completion:
- MRT extraction: 174/187 stations (93% complete)
- Remaining: 13 stations (mostly LRT + special codes)
- All major operational lines complete

---
**Last Updated**: 2026-02-03
**Created By**: opencode agent
**Next Agent**: Start with Batch 15A (NEL completion)