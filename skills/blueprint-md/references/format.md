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

walkthroughs:                         # optional, explained scenarios for walkthrough.html
  - title: Place an order             # tab name in the player
    summary: What the scenario shows. # optional
    steps:
      - from: customer                # a step moves along the connection between two components
        to: portal
        title: Submit the cart        # short, shown on the diagram and in the step list
        via: REST POST /orders        # optional: operation, protocol, event or queue
        detail: >                     # optional: what happens and why; `backticks` render as code
          The portal validates the cart and creates the order.
        code: [src/portal/orders.ts]  # optional: files involved, checked next to the YAML or in a parent folder
      - at: portal                    # a step that stays inside one component
        title: Show confirmation
# walkthroughs: walkthroughs.yaml     # or keep them in their own file (a list, or a mapping with 'walkthroughs:')

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

At a glance · Structure (group tree) · Components (about, building block with docs link, role, technology, group, code path, what it is not meant for, and Sends to / Receives from / Two-way with / Linked with) · Connections table · Flows · Walkthroughs · Decisions · Notes for coding agents.

## walkthrough.html

Written by `build` whenever the YAML has `walkthroughs:` or `flows:`. It is the diagram plus a player panel: each step highlights its components, animates the connection between them (in the step's direction, also against the arrow), leaves earlier steps as a faint trail and shows title, `via`, detail and code paths. Explicit walkthroughs come first; every flow without a walkthrough of the same title becomes a simple scenario whose step titles are the connection labels.

- A step between two components without a connection is drawn as a dashed virtual line and `build` warns. Add the connection if it exists in the system.
- Controls: Prev / Play / Next, `←` `→`, `space`, `1`–`9` for the scenario, `f` fit / 100 %, `esc` reset. `walkthrough.html#2-5` opens scenario 2 at step 5.
- The diagram page links to the walkthrough in its footer.
- `build --gif` records the first scenario as `walkthrough.gif` and `walkthrough-dark.gif` (Playwright + Pillow). `window.walkthrough` (`select`, `go`, `fit`, `pause`, `dot`) lets other scripts drive the player.
