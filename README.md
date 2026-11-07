# blueprint-md

**Architecture as code, for people and coding agents.**

Describe a system in one small YAML file, or let your AI agent design it with you. blueprint-md turns that file into a clean architecture diagram with real logos, plus an `ARCHITECTURE.md` that tells a coding agent exactly what each component does and what it may talk to.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="examples/order-to-cash/architecture-dark.png">
  <img alt="Order-to-Cash architecture: a B2B customer orders in Experience Cloud, Sales Cloud publishes order events, MuleSoft process and system APIs create the order in SAP S/4HANA, and invoice status flows back in an hourly batch" src="examples/order-to-cash/architecture.png">
</picture>

## Why

Diagrams drawn by hand go stale, and pictures mean nothing to a coding agent. blueprint-md keeps one text file as the source of truth:

```
architecture.yaml  ──build──▶  architecture.html / .png   for people
                         └──▶  ARCHITECTURE.md            for coding agents
```

- **Readable and diff-able:** the architecture lives in git next to the code.
- **Meaningful connections:** every line says what flows, over which protocol, with which payload.
- **Decisions included:** context, choice, alternatives and consequences are part of the file and the document.
- **Agent-ready:** hand `ARCHITECTURE.md` to Claude Code, Cursor or Codex as the plan for building the project.

## What it looks like

```yaml
title: Order-to-Cash

groups:
  sf:   {label: Salesforce Org, icon: salesforce, color: blue}
  mule: {label: MuleSoft Anypoint, icon: lucide:workflow, color: teal}

components:
  sales:
    type: salesforce/sales-cloud        # building block from the catalog
    group: sf
    at: [1, 1]
    about: System of record for accounts and orders.
  events:
    type: salesforce/platform-event
    name: Order Events                  # project-specific name
    group: sf
    at: [2, 1]
  process:
    type: mulesoft/process-api
    name: Order Process API
    group: mule
    at: [3.5, 1]

connections:
  - sales -> events: order activated
    primary: true
  - events -> process: subscribe
    primary: true
    protocol: Pub/Sub API (gRPC)

decisions:
  - title: Platform Events instead of polling
    status: accepted
    alternatives: [Scheduled polling (API limits), Outbound messages (no replay)]
```

More examples: [`examples/salesforce-to-aws/`](examples/salesforce-to-aws/) shows Salesforce events processed on AWS with the official AWS icons.

See the full example in [`examples/order-to-cash/`](examples/order-to-cash/): the [YAML](examples/order-to-cash/architecture.yaml), the [generated ARCHITECTURE.md](examples/order-to-cash/ARCHITECTURE.md) and the [interactive HTML](examples/order-to-cash/architecture.html). The full format is in [`skills/blueprint-md/references/format.md`](skills/blueprint-md/references/format.md).

## Building block catalog

The catalog lists the parts you can use, so people and agents share one vocabulary. Each entry says what the block is, when to use it, when not to, and links to the official documentation:

```bash
python3 skills/blueprint-md/scripts/blueprint.py catalog            # list everything
python3 skills/blueprint-md/scripts/blueprint.py catalog event      # search
```

- **Browse it:** [`skills/blueprint-md/catalog/README.md`](skills/blueprint-md/catalog/README.md)
- **Included (139 blocks):** Salesforce and MuleSoft (clouds, Flow, Apex, Platform Events, Change Data Capture, Pub/Sub API, Named Credentials, API-led layers…), AWS, Microsoft Azure and Google Cloud (compute, storage, databases, integration, networking, security, analytics and AI), and generic blocks (user, service, database, queue, scheduler…)
- **Use it:** `type: salesforce/platform-event` on a component fills in name, role and icon, and ARCHITECTURE.md adds the description, docs link and what the block is not meant for
- **Extend it:** add `catalog/<domain>.yaml` to the skill, or `catalogs: [my-blocks.yaml]` to one project
- **Keep it current:** entries hold only stable facts and link to the official docs for details that change. Each entry has a `checked: YYYY-MM` date. `blueprint.py catalog --check` validates every entry, flags entries not reviewed for six months, and opens every docs link in a headless browser. A GitHub Action runs it every month and whenever the catalog changes.

## Official cloud icons

AWS, Azure and Google Cloud components use the vendors' **official architecture icons**, not community copies:

| Vendor | Package | Write |
|---|---|---|
| AWS | [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) | `icon: aws:lambda` |
| Microsoft Azure | [Azure architecture icons](https://learn.microsoft.com/azure/architecture/icons/) | `icon: azure:function apps` |
| Google Cloud | [Google Cloud icons](https://cloud.google.com/icons) | `icon: gcp:bigquery` |

Each package is downloaded once from the vendor's site into `~/.cache/blueprint-md/packs/` (the newest AWS and Azure release is found automatically) and indexed by name. Search it with `blueprint.py icons aws lambda`; refresh it with `--update`. Icons are only embedded into the diagrams you build and are never stored in this repo. Each vendor's terms apply to its icons.

## Use it with an AI agent

blueprint-md is an [agent skill](https://agentskills.io). Install it for Claude Code:

```bash
git clone https://github.com/Sav019/blueprint-md.git
mkdir -p ~/.claude/skills
ln -s "$(pwd)/blueprint-md/skills/blueprint-md" ~/.claude/skills/blueprint-md
```

Then just ask:

> Let's design the architecture for syncing orders from Salesforce to SAP. Ask me what you need to know.

The agent asks about volumes, timing, data ownership and authentication, proposes options with trade-offs, records your decisions, and writes and builds the YAML. Ask it to "just draw it" and it decides on its own and marks its choices as proposed decisions for you to review.

## Use it from the command line

```bash
pip install pyyaml                      # required
pip install playwright && python3 -m playwright install chromium   # only for PNGs

python3 skills/blueprint-md/scripts/blueprint.py build architecture.yaml --png
python3 skills/blueprint-md/scripts/blueprint.py check architecture.yaml
```

`build` writes `architecture.html`, `ARCHITECTURE.md` and, with `--png`, light and dark PNGs. `check` validates the file and reports layout problems such as overlapping groups, lines crossing components, or labels without room. Icons are fetched on first use from svgl, devicon, gilbarbara/logos and Lucide, and cached in `.blueprint/` next to the YAML.

## Roadmap

- [x] Building block catalog with docs links and automatic link checks
- [x] Catalogs for AWS, Azure and Google Cloud with the official icon sets
- [ ] More catalogs: SAP, Microsoft 365, data platforms
- [ ] Project scaffolding from the YAML (starting with Salesforce SFDX projects)
- [ ] Mermaid and C4 export
- [ ] Official Salesforce architecture icon set
- [ ] Several views (overview and detail) from one model
- [ ] Interactive canvas for editing with an agent

## License

MIT. Brand logos fetched at build time remain the trademarks of their owners.
