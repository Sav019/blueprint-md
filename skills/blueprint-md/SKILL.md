---
name: blueprint-md
description: "Design a software or integration architecture with the user and capture it as one architecture.yaml, then build a diagram (HTML/PNG with real logos) and an ARCHITECTURE.md that coding agents can follow. Use when the user wants an architecture / system / integration / stack diagram, wants to brainstorm or decide on an architecture, or wants an architecture written down as instructions for building a project, including Salesforce, MuleSoft, cloud and SaaS integrations."
license: MIT
compatibility: Python 3.9+ with PyYAML; network access to fetch icons on first use; Playwright + Chromium for PNG output
---

# blueprint-md

One YAML file describes the architecture. One command turns it into:

- `architecture.html`: a self-contained diagram (light/dark, hover a node for details)
- `architecture.png` and `architecture-dark.png` (with `--png`)
- `ARCHITECTURE.md`: every component, what it does, what it talks to and why, plus flows and decisions, written for coding agents

The YAML is the source of truth. Never edit the generated files by hand.

```bash
python3 <skill>/scripts/blueprint.py build architecture.yaml --png
python3 <skill>/scripts/blueprint.py check architecture.yaml   # warnings only, writes nothing
```

## Workflow

1. **Understand the system.** Choose the mode from how the user asks:
   - **Guided** (default when anything important is open): ask a few focused questions, at most 3–4 at a time. Typical ones: which systems are involved, who uses it, data volumes, real-time vs. batch, which system owns which data, authentication, middleware, hosting. For each real architecture choice, offer 2–3 options with their trade-offs and a recommendation, and let the user decide.
   - **Auto** (the user says "just draw it" or gives a complete description): decide sensibly yourself and record every non-obvious choice as a decision with `status: proposed` so the user can review it.
2. **Write `architecture.yaml`** in the user's project folder (or where they ask). The format is in `references/format.md`; read it before writing the first file.
3. **Build and look.** Run `build ... --png`, fix every warning, then open the PNG and check it yourself: no line through text, labels readable, groups not overlapping, nothing cramped. Rearrange `at:` positions and rebuild until it is clean.
4. **Deliver** the diagram and `ARCHITECTURE.md`. Mention that changes go into the YAML followed by a rebuild.
5. **Iterate.** For every change the user asks for, edit the YAML, rebuild, look again.

## Writing a good architecture.yaml

- **Components** are things that run or store data: apps, services, APIs, databases, queues, SaaS products, people. One component = one responsibility. Give each an `about:` sentence: it becomes the agent's instruction.
- **Groups** are boundaries: a vendor org or account, a cloud, a runtime, a team, a repo. Nest at most one or two levels.
- **Connections** carry meaning: the label says *what* flows (`creates order`, not `calls`), `protocol:` and `data:` say how and which payload. Use `->` for calls, `..>` for async or batch, `<->` for two-way, `--` for a plain link. Mark the main end-to-end path with `primary: true` (one continuous chain reads best).
- **Flows** list the steps of the main scenarios. **Decisions** capture every real choice: context, decision, alternatives, consequences. The user's answers in guided mode become decisions.
- **notes:** holds project conventions for coding agents (repo layout, naming, security rules).
- Component ids are stable names that coding agents reuse for folders and modules: short, lowercase, no spaces (`order-api`, `crm`).

## Layout

Components sit on a grid: `at: [column, row]`, one step = 200 × 190 px (change it with `grid:`). Half steps are fine (`at: [3.5, 1]`).

- Put the main flow on one row, left to right. Put supporting components above or below the component they serve.
- Sibling groups need space between them: leave a column or row free, or use half steps. `check` warns about overlaps.
- Routing is automatic and avoids components, group labels and other lines. If a line still crosses something, the build prints a warning: move components, or force a route with `route:` (the warning lists the possible values).

## Icons

`icon:` accepts:

- a brand name such as `salesforce`, `sap`, `postgresql`, `react`: looked up in svgl, then devicon, then gilbarbara/logos
- `lucide:<name>` for concepts without a brand (`lucide:user`, `lucide:zap`, `lucide:database`, `lucide:clock`; see lucide.dev/icons)
- `svgl:<name>`, `devicon:<name>` or `logos:<name>` to force one source
- a URL or a local `.svg`/`.png` path (relative to the YAML)

Icons are cached in `.blueprint/icons/` next to the YAML; `--offline` uses only the cache. A missing icon prints a warning and shows a monogram, so try another name. Never recolor brand logos. If a logo is white, use `tile: dark`. For wide logos, use `tile: wide`.

## Confidentiality

Architectures often describe a customer's or employer's internal systems. Keep everything local; don't upload diagrams or YAML to online services unless the user asks.
