# Design decisions

## Why an immutable evidence snapshot?

The agent should investigate a consistent view of an incident. The control API serializes operations and supplies a copied snapshot to the investigator. A new scenario starts a new generation. Approvals require a diagnosis from that generation. Collecting more traffic clears the prior report.

## Why a transparent rules baseline?

A model must justify its complexity against a cheap alternative. Rules cover known faults; the single-pass mode isolates the value of interactive tool use. They share the same bounded evidence functions. The model receives no injected scenario name, but knows the category vocabulary. Avoid claiming the lab proves general incident response ability.

## Why standard-library Python?

The first version prioritizes reproducibility: HTTP requests, SQLite writes, a tool loop, a dashboard and tests work without dependency installation. The tradeoff is limited production infrastructure. ThreadingHTTPServer is suitable only for this local lab. A production system should separate services, persist bounded telemetry, isolate users, and use mature telemetry and server infrastructure.

## What does citation validation guarantee?

It rejects nonexistent or unobserved evidence IDs. It does not validate entailment, causal reasoning, or the truth of model prose. Assess those separately with annotated evaluations. The system does not use model-generated confidence percentages.

## Why reset all lab faults?

The recovery action has a small, well-defined scope and requires an operator click. Five fresh checkout probes establish an observable postcondition. The reset does not prove the proposed root cause was correct; the evaluator scores diagnosis separately. A real remediation system needs action-specific authorization, rollback and blast-radius controls.

## Current limitations

- Only five fault families plus healthy traffic; rules have been developed for these families.
- Handlers share one process; no Kubernetes, Kafka, cloud deployment or OpenTelemetry integration is claimed.
- Sequential synthetic checkout traffic; throughput under load is not measured.
- Small latency samples are sensitive to machine and filesystem scheduling.
- No authentication or public deployment; the app binds to localhost and checks Host/Origin.
- No explicit dollar-denominated API budget; turns, output tokens, timeouts and tools are bounded.
- Model calls may take several minutes at the maximum turn budget; the UI waits for completion.
- No server-side cancellation or model repair loop for invalid JSON; invalid output fails explicitly.
- Repeated probes retain events in memory until the next scenario. Run short lab sessions.
- Live AI responses and provider compatibility require testing with the user's selected model.

## Questions to be able to answer in an interview

1. What evidence distinguishes a payment outage from retry amplification?
2. Why does an error-rate-only detector miss a successful but slow request path?
3. How does a deployment correlation differ from causal evidence?
4. Which validation happens in code, and which still needs an evaluator?
5. What would change when moving from local handlers to independent services?
6. Why can recovery pass even when a diagnosis was wrong?
7. When would you choose a rules system over an LLM?
