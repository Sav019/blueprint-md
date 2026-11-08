# Requirements checklist

Use it to find the questions that matter for *this* case. Ask only those whose answer would change which option wins or how it is built; at most 3–4 at a time, each with a short "why it matters".

## Business
- Who uses the result (employees, customers, partners, systems), how many, and through which channel?
- What is the business outcome, and how will success be measured?
- Is there a deadline or a first release that must come early? What can come later?
- What happens today (manual process, existing tool)? What must keep working during the change?

## Data
- Which systems hold the data, and which one is the source of truth for each object?
- Structured or unstructured (records, files, PDF, HTML, images, events)? Formats and sizes?
- Volumes now and in 2–3 years: records, files, events per day, peaks.
- Freshness: real time, minutes, hourly, daily? What happens if it is stale?
- Data quality: duplicates, missing keys, matching rules between systems?
- Retention and deletion: how long is data kept, and what must happen when it is deleted at the source?

## Integration
- Direction and trigger: push or pull, event or schedule, request-reply or fire-and-forget?
- Which APIs, connectors or middleware exist and are licensed? Rate limits and quotas?
- Error handling: retries, replay, dead letters, who is alerted, and who fixes it?
- Ordering and idempotency: can messages arrive twice or out of order?

## Security and compliance
- Who may see what? Do access rules from the source have to apply downstream (per user, per role, per region)?
- Authentication between systems (OAuth flows, certificates, service accounts) and where secrets live.
- Personal or sensitive data (PII, health, financial)? Masking, encryption, consent?
- Data residency and regulations (GDPR, HIPAA, industry rules); audit trail requirements.
- For AI: may data be sent to an LLM, under which trust and retention terms? Must answers cite sources?

## Platform and constraints
- Which products and editions are licensed, and which are off limits? Consumption-based pricing (credits, calls, storage)?
- Mandated platforms or vendors (cloud, middleware, identity provider)?
- Team skills: who builds it, who runs it after go-live? Low-code versus pro-code preference?
- Environments and release process (sandboxes, CI/CD, change approval).

## Quality attributes
- Availability and recovery: acceptable downtime, recovery time and data loss?
- Performance: response time targets, concurrent users, batch windows.
- Scalability: expected growth; limits that would force a redesign.
- Observability: what must be monitored, logged and reported?
- Cost: budget ceiling for licenses, consumption and operations.
