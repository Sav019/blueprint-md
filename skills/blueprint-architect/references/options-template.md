# architecture-options.md template

Copy this structure. Keep it short where the case is simple; never drop the requirement fit or the limitations.

```markdown
# <Title>: architecture options

Status: draft | decided (<date>, <who>) · Last updated: <date>

## Goal
<One or two sentences in business terms.>

## Requirements
| ID | Requirement | Priority | Source |
|---|---|---|---|
| R1 | Agents answer questions using the PDF and HTML manuals | must | business |
| Q1 | A changed document is used within 1 hour | should | business |
| Q2 | Restricted documents are visible only to HR | must | inferred, to confirm |

## Constraints
| ID | Constraint |
|---|---|
| C1 | Documents stay in Google Cloud Storage (owned by the content team) |
| C2 | Salesforce Data 360 and Agentforce are licensed; no new vendors |

## Assumptions
| ID | Assumption | Confirm with |
|---|---|---|
| A1 | Fewer than 10,000 files, under 50 MB each | content team |

## Options

### Option A: <name>
**Idea:** <one sentence>

**How it works**
1. …
2. …

**Building blocks:** <catalog types> · **New:** <what has to be bought, built or operated>

| Req. | Fit | Note |
|---|---|---|
| R1 | ✅ | |
| Q1 | ⚠️ | only with the notification pipeline |
| Q2 | ❌ | the index has no per-user filtering |
| C1 | ✅ | |

**Limitations and risks**
- <limitation or risk> (likelihood · impact) → <mitigation>

**Cost and effort:** licenses/consumption: … · build: S/M/L · run: <who operates it>
**Lock-in:** <how hard to change course>
**Facts:** verified: <claim> ([docs](…)) · assumed: <claim>

### Option B: <name>
…

## Comparison
Options failing a **must** or a hard constraint: <option and why>, out.

| | Option A | Option B | Option C |
|---|---|---|---|
| Requirements met | 5/6 | 6/6 | 6/6 |
| Cost | low | medium | high |
| Build effort | S | M | L |
| Run effort | … | … | … |
| Main risk | … | … | … |
| Time to first release | … | … | … |

## Recommendation
**Option B**, because:
1. …
2. …

Accepted risk: … · Would change if: …

## Open points
| # | Question | Blocks | Who answers |
|---|---|---|---|
| 1 | … | build / decision | … |

## Decision
<Chosen option, date, who decided, conditions. Then: drawn as architecture.yaml with blueprint-md.>
```
