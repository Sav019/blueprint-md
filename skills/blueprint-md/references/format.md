# architecture.yaml format

```yaml
title: Order-to-Cash                  # diagram and document title
summary: >                            # 1–3 sentences, shown under the title
  What the system does in plain words.
grid: {col: 200, row: 190}            # optional, px per grid step
catalogs: [my-blocks.yaml]            # optional, extra building-block files (relative to this YAML)

groups:                               # optional
  <group-id>:
    label: Salesforce Org             # shown in the top-left corner
    icon: salesforce                  # optional, see "Icons" in SKILL.md
    color: blue                       # blue | orange | violet | green | teal | red | pink | gray
    parent: <group-id>                # optional, nests this group inside another
    dashed: true                      # optional, dashed outline without fill
    about: Single production org.     # optional, goes into ARCHITECTURE.md

components:                           # required
  <component-id>:
    type: salesforce/sales-cloud      # optional, building block from the catalog: fills name, kind and icon
    name: Sales Cloud                 # display name (overrides the catalog)
    kind: accounts · orders           # short role under the name (lowercase reads best)
    icon: salesforce
    group: <group-id>                 # optional
    at: [1, 1]                        # required: [column, row], half steps allowed
    tile: dark                        # optional: dark (for white logos) | wide | bare
    about: What it does and owns.     # instruction text for agents; also the hover tooltip
    tech: Apex, LWC                   # optional
    code: force-app/main/default      # optional, where the code lives / will live

connections:                          # optional
  - <from> -> <to>: label             # what flows, in a few words
    primary: true                     # optional, part of the main flow (accent color)
    protocol: REST, OAuth 2.0         # optional
    data: Order__c                    # optional, payload / object / event
    about: Longer explanation.        # optional
    route: hv                         # optional, force a route (build warnings list options)

flows:                                # optional, ordered steps of a scenario
  Order placed online: [customer, portal, sales, events]

decisions:                            # optional, lightweight decision records
  - title: Platform Events instead of polling
    status: accepted                  # proposed | accepted | superseded …
    context: Why a decision was needed.
    decision: What was chosen.
    why: Reasoning (optional).
    alternatives: [Option B (reason), Option C (reason)]
    consequences: What follows from it.

notes: |                              # optional, conventions for coding agents
  Repo layout, naming rules, security rules.

legend:                               # optional, rename legend entries
  primary: order flow
  default: sync call
  dashed: batch
```

## Connection operators

| Operator | Meaning | Drawn as |
|---|---|---|
| `a -> b` | a calls / sends to b | solid line, arrow at b |
| `a <-> b` | two-way exchange | solid line, arrows at both ends |
| `a ..> b` | async, event or batch | dashed line, arrow at b |
| `a <..> b` | async in both directions | dashed line, arrows at both ends |
| `a -- b` | related, no direction | solid line, no arrows |

Write each connection as one list item: `- crm -> erp: create order`. If the label contains `:` or `#`, quote it: `- crm -> erp: "orders: create"`.

## Routes

The router tries several routes for each connection and picks the shortest one that avoids components, group labels and other lines:

- same row: `h` (straight), `detour-above`, `detour-below` (plus `+`/`-` variants with shifted ends)
- same column: `v` (straight), `detour-left`, `detour-right`
- otherwise: `hv` (sideways, then up/down), `vh` (up/down, then sideways), `hvh0`/`hvh1`/`hvh2` (through a vertical corridor), `vhv` (through the band between rows)

Set `route:` only when the automatic choice looks wrong.

## Catalog entries

A catalog file (`catalog/<domain>.yaml`) looks like this:

```yaml
title: Salesforce & MuleSoft
entries:
  salesforce/platform-event:
    name: Platform Event
    kind: event bus
    category: Integration
    icon: lucide:zap
    what: Publish/subscribe messages inside Salesforce and to external subscribers.
    use_when: Fire-and-forget notifications to other systems in near real time.
    avoid_when: Request-reply calls that need an immediate answer, or bulk data loads.
    connects_with: [salesforce/pub-sub-api, mulesoft/process-api]
    docs: https://developer.salesforce.com/docs/platform/platform-events/guide/platform-events-intro.html
    checked: 2026-11
```

Only `name` and `what` are required. Non-generic entries should have `docs` and `checked`; `blueprint.py catalog --check` reports entries not reviewed for more than six months.

## ARCHITECTURE.md sections

At a glance · Structure (group tree) · Components (about, building block with docs link, role, technology, group, code path, what it is not meant for, and Sends to / Receives from / Two-way with / Linked with) · Connections table · Flows · Decisions · Notes for coding agents.
