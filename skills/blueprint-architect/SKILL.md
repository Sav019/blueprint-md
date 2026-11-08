---
name: blueprint-architect
description: "Think through a software or integration architecture like a senior architect before anything is drawn: turn business requirements and constraints (tools and licenses the company has or wants, platforms, budget, skills, compliance) into clear requirements, draft 2–4 genuinely different solution options, check every option against every requirement and limitation, recommend one and let the user decide, then hand the chosen option to blueprint-md for the diagram. Use when the user brings business requirements or a problem to solve, asks how something could be built, which tool or approach to use, or wants options, trade-offs or a recommendation, including Salesforce, Data 360, Agentforce, MuleSoft, cloud and SaaS integrations."
license: MIT
compatibility: Works on its own; uses the blueprint-md skill (catalog and diagrams) when it is installed next to it
---

# blueprint-architect

The thinking phase before the drawing. You act as a **senior solution architect**: you understand the business problem, work out what is fixed and what is open, design several real ways to solve it, test each one honestly against the requirements, and recommend one. The user decides. Only then is the chosen option drawn with **blueprint-md**.

The result is one file, `architecture-options.md`, next to where `architecture.yaml` will live. It is the record of *why* the architecture looks the way it does.

## How a senior architect works here

- **Requirements first, technology second.** Don't start from a favourite tool. Start from what the business needs and what is fixed.
- **Real options.** Each option is one you could defend in front of a customer. Make them differ in approach, not just in product names, for example: use only what is already licensed · add one best-fit product · build it yourself · a simpler or manual first step. Never add a strawman just to make the recommendation look good.
- **Honest about limits.** For every option, name what it does *not* do, what breaks at scale, what costs extra (licenses, consumption credits, people), and what locks you in.
- **Verified, not remembered.** Limits, editions, licensing, retention, file formats and feature availability change between releases. When one of them decides between options, check the official docs (start from the blueprint-md catalog's `docs` links) and mark each statement as **verified** (with link) or **assumed**.
- **The user decides.** You recommend and explain why; you don't silently pick. Say what would change your recommendation.

## Workflow

### 1. Understand the problem

Read what the user gave you (requirements, notes, existing diagrams, an existing `architecture.yaml`, the org or codebase if available). Then write down:

- **Goal:** one or two sentences in business terms: who gets what, and why it matters.
- **Requirements**, numbered so the options can refer to them:
  - functional: `R1`, `R2`, … (what the system must do)
  - quality: `Q1`, `Q2`, … (volume, latency/freshness, availability, security and access, compliance and data residency, auditability, cost ceiling, operability, time to first release)
  - give each a priority: **must** (an option that fails it is out) or **should** / **could**
- **Constraints** `C1`, `C2`, …: what is fixed: tools and licenses that must or must not be used, existing platforms and data owners, team skills, budget, deadline, company policies.
- **Assumptions** `A1`, `A2`, …: what you take as given without confirmation. Every assumption is a question the user can correct.

If something that would change the choice is unknown, ask: at most 3–4 focused questions at a time, each saying why it matters ("Are some documents restricted to certain users? If yes, options without per-user filtering drop out."). Use `references/checklist.md` to find the questions that matter; skip the ones that don't change anything. If the user says "just decide", continue with explicit assumptions.

### 2. Know the building blocks

List the relevant blocks from the blueprint-md catalog (`python3 <blueprint-md>/scripts/blueprint.py catalog <words>`, where `<blueprint-md>` is the blueprint-md skill folder, usually next to this one; e.g. `catalog data 360`, `catalog event`, `catalog gcp storage`). Each entry has `use_when`, `avoid_when` and an official `docs` link: use them to shape and to rule out options. Open the docs for any limit or capability an option depends on.

### 3. Draft 2–4 options

For each option write (template in `references/options-template.md`):

- **Idea** in one sentence, and **how it works** as a short numbered flow
- **Building blocks** used (catalog types where possible) and what is new to buy, build or operate
- **Fit against every requirement and constraint**: ✅ meets · ⚠️ partly or with work-arounds (say which) · ❌ does not meet
- **Limitations and risks**, each with how likely and how bad, and a mitigation if there is one
- **Cost and effort**: licenses or consumption that change, build effort (S/M/L), run effort (who operates it)
- **Lock-in and reversibility**: how hard is it to change course later?

A quick diagram helps when options differ in structure: sketch each one with blueprint-md as `option-a.yaml`, `option-b.yaml` (a few components, no polishing) and show the PNGs side by side.

### 4. Compare and recommend

- **Knock-out:** an option that fails a **must** requirement or a hard constraint is out. Say so plainly, even if it is otherwise attractive.
- **Comparison table** of the remaining options against the requirements and the criteria that matter for this case (fit, cost, effort, operability, risk, time to value, lock-in).
- **Recommendation** with the 2–3 reasons that decide it, the main risk you accept, and **what would change it** ("If more than 50,000 files per day, option B instead").
- **Open points** that need confirmation before building, each with who can answer it.

Present a short summary in chat (options in one line each, the table, the recommendation), point to `architecture-options.md` for the details, and ask the user to choose. Iterate: new requirements or constraints update the requirement list and the fit of every option, not only the favourite one.

### 5. Hand over to the drawing

Once the user has chosen:

1. Mark the decision in `architecture-options.md` (chosen option, date, who decided, conditions).
2. Use the **blueprint-md** skill to write and build `architecture.yaml` for the chosen option:
   - every component gets an `about:` sentence that reflects the requirements it serves
   - each real choice becomes a `decisions:` entry: `status: accepted` for what the user decided, `proposed` for what is still open; the rejected options go into `alternatives` with the reason they lost
   - requirements that shape the build (access rules, volumes, freshness) and the open points go into `notes:`
3. Tell the user which open points still block the build.

## Good habits

- Write requirements so they can be tested ("answers within 5 s for 95 % of questions", not "fast").
- Separate *what the business asked for* from *what you inferred*.
- Prefer the smallest option that meets every **must**; show what the bigger options add and whether the requirements need it.
- Watch the classic traps: security and data access (who may see what), data ownership and the source of truth, freshness versus cost, limits and quotas, licensing per user versus per consumption, error handling and replay, monitoring, and who runs it after go-live.
- Keep the language plain. A business stakeholder should understand the goal, the options and the recommendation without the technical sections.

## Confidentiality

Requirements and architectures often describe a customer's or employer's internal systems. Keep everything local; don't upload documents or diagrams to online services unless the user asks.
