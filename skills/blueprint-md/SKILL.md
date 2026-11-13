---
name: blueprint-md
description: "Design a software or integration architecture with the user and capture it as one architecture.yaml, then build a diagram (HTML/PNG with real logos), an interactive step-by-step walkthrough of the main scenarios, and an ARCHITECTURE.md that coding agents can follow. Use when the user wants an architecture, system or integration diagram or a tech stack overview, wants to see step by step what happens in a system (for example when a user performs an action), wants to brainstorm or decide on an architecture, or wants an architecture written down as instructions for building a project, including Salesforce, MuleSoft, cloud and SaaS integrations."
license: MIT
compatibility: Python 3.9+ with PyYAML; network access to fetch icons on first use; Playwright + Chromium for PNG output
---

# blueprint-md

One YAML file describes the architecture. One command turns it into:

- `architecture.html`: a self-contained diagram (light/dark, hover a node for details)
- `architecture.png` and `architecture-dark.png` (with `--png`)
- `ARCHITECTURE.md`: every component, what it does, what it talks to and why, plus flows, walkthroughs and decisions, written for coding agents
- `walkthrough.html`: an interactive step-by-step tour of the main scenarios on the same diagram (written when the YAML has `walkthroughs:` or `flows:`)

The YAML is the source of truth. Never edit the generated files by hand.

```bash
python3 <skill>/scripts/blueprint.py build architecture.yaml --png
python3 <skill>/scripts/blueprint.py check architecture.yaml   # warnings only, writes nothing
```

## Workflow

0. **Know the building blocks.** Before designing, list the catalog: `blueprint.py catalog` (all) or `blueprint.py catalog <words>` (search, e.g. `catalog event`, `catalog salesforce api`). Each entry says what the block is, when to use it, when not to, and links to the official docs. Base your proposals on these entries. When a decision depends on details that change between releases (limits, retention, pricing), open the entry's docs link to confirm them instead of relying on memory.
1. **Understand the system.** If the user brings business requirements and the solution itself is still open (which tools, which approach), use the **blueprint-architect** skill first: it drafts and compares options, and the chosen one comes back here to be drawn. Otherwise choose the mode from how the user asks:
   - **Guided** (default when anything important is open): ask a few focused questions, at most 3–4 at a time. Typical ones: which systems are involved, who uses it, data volumes, real-time vs. batch, which system owns which data, authentication, middleware, hosting. For each real architecture choice, offer 2–3 options with their trade-offs and a recommendation, and let the user decide.
   - **Auto** (the user says "just draw it" or gives a complete description): decide sensibly yourself and record every non-obvious choice as a decision with `status: proposed` so the user can review it.
2. **Write `architecture.yaml`** in the user's project folder (or where they ask). The format is in `references/format.md`; read it before writing the first file.
3. **Build and look.** Run `build ... --png`, fix every warning, then open the PNG and check it yourself: no line through text, labels readable, groups not overlapping, nothing cramped. Rearrange `at:` positions and rebuild until it is clean.
4. **Write walkthroughs** for the 2–5 scenarios users care most about (see below), rebuild, and fix every walkthrough warning.
5. **Deliver** the diagram, `walkthrough.html` and `ARCHITECTURE.md`. Mention that changes go into the YAML followed by a rebuild.
6. **Iterate.** For every change the user asks for, edit the YAML, rebuild, look again.

## Writing a good architecture.yaml

- **Components** are things that run or store data: apps, services, APIs, databases, queues, SaaS products, people. One component = one responsibility. Give each an `about:` sentence describing its job *in this project*: it becomes the agent's instruction.
- **Use `type:` whenever a catalog entry fits** (`type: salesforce/platform-event`). Name, role and icon then come from the catalog, and ARCHITECTURE.md adds the block's description, its docs link and what it is not meant for. Override `name:`/`kind:`/`icon:` only for project-specific wording. If nothing fits, use a `generic/...` type or a free component without `type:`, and tell the user which entry could be added to the catalog.
- **Groups** are boundaries: a vendor org or account, a cloud, a runtime, a team, a repo. Nest at most one or two levels.
- **Connections** carry meaning: the label says *what* flows (`creates order`, not `calls`), `protocol:` and `data:` say how and which payload. Use `->` for calls, `..>` for async or batch, `<->` for two-way, `--` for a plain link. Mark the main end-to-end path with `primary: true` (one continuous chain reads best).
- **Flows** list the steps of the main scenarios. **Decisions** capture every real choice: context, decision, alternatives, consequences. The user's answers in guided mode become decisions.
- **notes:** holds project conventions for coding agents (repo layout, naming, security rules).
- Component ids are stable names that coding agents reuse for folders and modules: short, lowercase, no spaces (`order-api`, `crm`).

## Walkthroughs

`walkthroughs:` turns scenarios into an interactive tour (`walkthrough.html`): every step moves along one connection (`from:`/`to:`) or stays in one component (`at:`), with a short title, an optional `via:` (operation, protocol, event, queue), a `detail:` and the `code:` files involved. Format in `references/format.md`. Plain `flows:` also appear in the tour, titled by connection labels, so even a quick architecture gets one.

- Pick the scenarios a newcomer would ask about: the main business flow end to end, then the most important secondary ones (an edit or admin task, an async or streaming path, an integration).
- One step = one hop that someone could point at in the code. Include the return path (response, event, subscription) so the scenario ends where the user sees the result.
- `detail:` says what happens and why in 1–3 sentences: validations, which data is read or written, retries, statuses, limits. Name real identifiers in `backticks` (operations, tables, classes, events).
- For an existing system, read the code before writing a step and list the files in `code:`; never describe behaviour you have not seen. A step without a matching connection usually means the diagram is missing (or wrongly has) a connection: fix the YAML, not the step.
- Long walkthroughs can live in their own file: `walkthroughs: walkthroughs.yaml`.
- After building, open `walkthrough.html` and click through each scenario, or check it headless with Playwright (no page errors; no step drawn as a dashed virtual line unless intended).

## Layout

Components sit on a grid: `at: [column, row]`, one step = 200 × 190 px (change it with `grid:`). Half steps are fine (`at: [3.5, 1]`).

- Put the main flow on one row, left to right. Put supporting components above or below the component they serve.
- Sibling groups need space between them: leave a column or row free, or use half steps. `check` warns about overlaps.
- Routing is automatic and avoids components, group labels and other lines. If a line still crosses something, the build prints a warning: move components, or force a route with `route:` (the warning lists the possible values).

## Icons

`icon:` accepts:

- a brand name such as `salesforce`, `sap`, `postgresql`, `react`: looked up in svgl, then devicon, then gilbarbara/logos
- `aws:<name>`, `azure:<name>`, `gcp:<name>`: the vendor's **official architecture icons** (`aws:lambda`, `aws:Amazon-Simple-Storage-Service`, `azure:function apps`, `gcp:bigquery`). Each package is downloaded once from the vendor's site into `~/.cache/blueprint-md/packs/` and never committed. Search names with `blueprint.py icons aws lambda`. Google publishes unique icons only for core products; other Google Cloud products use their category icon (`gcp:Integration Services`, `gcp:Databases`…), as Google's guidelines ask. Catalog entries for AWS, Azure and Google Cloud already point to the right icon, so prefer `type:`.
- `slds:<name>`: Salesforce's official **Lightning Design System** icons (standard set: `slds:data_cloud`, `slds:data_streams`, `slds:identifier`, `slds:segments`, `slds:flow`, `slds:apex`, `slds:agent_astro`). The glyph is shown on its official SLDS colour. Search names with `blueprint.py icons slds data`. Use them for Salesforce features; the `salesforce` logo stays for whole clouds and orgs.
- `lucide:<name>` for concepts without a brand (`lucide:user`, `lucide:zap`, `lucide:database`, `lucide:clock`; see lucide.dev/icons)
- `svgl:<name>`, `devicon:<name>` or `logos:<name>` to force one source
- a URL or a local `.svg`/`.png` path (relative to the YAML)

Icons are cached in `.blueprint/icons/` next to the YAML; `--offline` uses only the cache. A missing icon prints a warning and shows a monogram, so try another name. Never recolor brand logos. If a logo is white, use `tile: dark`. For wide logos, use `tile: wide`.

## The catalog

Building blocks live in `catalog/*.yaml` inside this skill (`generic`, `salesforce`, `aws`, `azure`, `gcp`, `data`, `enterprise`, `dev`, `identity`; one file per domain). A project can add its own with `catalogs: [my-blocks.yaml]` in its architecture.yaml. `catalog/README.md` is the browsable version, generated by `blueprint.py catalog --write catalog/README.md`.

When adding or editing an entry: keep `what`, `use_when` and `avoid_when` short and stable; put numbers that change between releases only behind the `docs` link; link the official documentation; set `checked: YYYY-MM` to the month you verified it; then run `blueprint.py catalog --check` (validates fields, review dates, `connects_with` references and every link) and regenerate `catalog/README.md`.

## Confidentiality

Architectures often describe a customer's or employer's internal systems. Keep everything local; don't upload diagrams or YAML to online services unless the user asks.
