# MRT Data Pipeline - Feature Specifications

## Overview

This directory contains comprehensive feature specifications for refactoring the MRT Data Pipeline. Each spec is designed to be self-contained and implementable by an agent with minimal guidance.

## Feature List

| Feature ID | Name | Priority | Effort | Dependencies |
|------------|------|----------|--------|--------------|
| [FEAT-001](./FEAT-001-project-restructure-and-contracts.md) | Project Restructure & Data Contracts | P0 | 1-2h | None |
| [FEAT-002](./FEAT-002-stage1-deterministic-ingestion.md) | Stage 1 - Deterministic Data Ingestion | P1 | 2-3h | FEAT-001 |
| [FEAT-003](./FEAT-003-stage2-enrichment-extraction.md) | Stage 2 - Enrichment Extraction Pipeline | P1 | 3-4h | FEAT-001, FEAT-002 |
| [FEAT-004](./FEAT-004-stage3-merger-validation.md) | Stage 3 - Data Merging & Validation | P1 | 2-3h | FEAT-001, FEAT-002, FEAT-003 |
| [FEAT-005](./FEAT-005-pipeline-orchestrator.md) | Pipeline Orchestrator & Configuration | P1 | 2-3h | FEAT-001, FEAT-002, FEAT-003, FEAT-004 |
| [FEAT-006](./FEAT-006-alerting-testing-automation.md) | Alerting, Testing & Automation | P2 | 3-4h | FEAT-001, FEAT-005 |
| [FEAT-007](./FEAT-007-stage2-incremental-checkpointing.md) | Stage 2 Incremental Checkpointing & Resume | P1 | 2-3h | FEAT-003 |

## Implementation Order

```
FEAT-001 (Foundation)
    ↓
FEAT-002 (Stage 1)
    ↓
FEAT-003 (Stage 2)
    ↓
FEAT-007 (Incremental Checkpointing)  # Can be done anytime after FEAT-003
    ↓
FEAT-004 (Stage 3)
    ↓
FEAT-005 (Orchestrator)
    ↓
FEAT-006 (Operations)
```

**Notes:**
- FEAT-006 can be started after FEAT-005 is complete and FEAT-001 is in place
- FEAT-007 can be started anytime after FEAT-003 is complete (enhances Stage 2)

## Quick Start for Implementers

1. **Start with FEAT-001** - This is the foundation. Don't skip it.
2. **Implement stages sequentially** - Each stage depends on the previous
3. **Run tests after each feature** - Validate before moving on
4. **Use the orchestrator** - Once FEAT-005 is done, use it to run the full pipeline

## Common Patterns

### Running a Single Stage
```bash
python src/orchestrator.py --stage 1
```

### Running Full Pipeline
```bash
python src/orchestrator.py
```

### Resuming from Stage 2
```bash
python src/orchestrator.py --resume-from 2
```

### Validating Output
```bash
python scripts/validate_output.py outputs/latest/stage3_final.json
```

## Key Design Decisions

1. **3-Stage Pipeline**: Clear separation between deterministic data (Stage 1), enrichment extraction (Stage 2), and merging/validation (Stage 3)

2. **Data Contracts**: All inter-stage communication uses Pydantic schemas for type safety and validation

3. **Checkpoint System**: Each stage saves its output, enabling resume capability

4. **Configuration-Driven**: All behavior configurable via `config/pipeline.yaml`

5. **Human-in-the-Loop**: Design acknowledges that final data requires human vetting, focuses on reliable, auditable pipeline

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    PipelineOrchestrator                     │
│                         (FEAT-005)                          │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ↓            ↓            ↓
┌──────────────┐ ┌──────────┐ ┌──────────┐
│ Stage 1      │ │ Stage 2  │ │ Stage 3  │
│ Ingestion    │ │ Enrich   │ │ Merge    │
│ (FEAT-002)   │ │(FEAT-003)│ │(FEAT-004)│
└──────┬───────┘ └────┬─────┘ └────┬─────┘
       │              │            │
       ↓              ↓            ↓
┌──────────────┐ ┌──────────┐ ┌──────────┐
│ data.gov.sg  │ │ Fandom   │ │ Merged   │
│ OneMap       │ │ OpenRouter│ │ Output  │
└──────────────┘ └──────────┘ └──────────┘
```

## Success Criteria for Full Implementation

- [ ] All 7 features implemented
- [ ] Full pipeline runs successfully: `python src/orchestrator.py`
- [ ] Output validates: `python scripts/validate_output.py`
- [ ] Tests pass: `python -m pytest tests/`
- [ ] Quarterly cron job configured and tested
- [ ] All 187 stations processed
- [ ] Human can vet final output
- [ ] Stage 2 can resume after 45-minute timeout (FEAT-007)

## Questions?

Refer to individual feature specs for detailed implementation guidance. Each spec includes:
- Full context and background
- Detailed requirements
- Code examples and pseudocode
- Success criteria with checkboxes
- Dependencies and known issues
