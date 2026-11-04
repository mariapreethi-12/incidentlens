# A one-minute demo

1. Start the app with `python -m incidentlens.server`.
2. Select **Retry amplification**, then inject and collect traffic.
3. Point out eight checkout requests versus thirty-two failing payment requests.
4. Run the rules baseline, or the AI agent after configuring and evaluating a live model.
5. Expand `read_traces` and show four payment attempts sharing the same checkout trace ID.
6. Click a citation to inspect its observed record.
7. Approve the lab reset. Show five fresh checkouts passing verification.
8. Export the JSON report.

Do not call a baseline recording an AI agent recording. For the AI version, show model identity, tool usage, token usage, and an actual successful model-backed run.

## LinkedIn draft for the current version

I built IncidentLens, a local lab for evidence-driven incident investigation.

The checkout app can fail in five controlled ways: a database lock, a payment outage, slow inventory, a checkout regression, and retry amplification. These produce actual HTTP responses, SQLite failures and measured request traces.

The investigation interface exposes the evidence behind a diagnosis and requires an operator to approve recovery. Five fresh checkouts verify the result.

The rules baseline passed 18/18 controlled trials. Next I am evaluating the tool-calling AI investigator against the same evidence in a single prompt, including failures and cost. The baseline result is not a claim about AI accuracy.

[Add your repository URL and a short recording. Tag a provider only when the recording or results actually use its technology.]

## Ownership and development

Present the project under your name and account. Understand the architecture, reproduce the measurements, and explain the tradeoffs. Describe AI development assistance honestly when relevant. Keep commit history factual; do not fabricate historical development dates or performance claims.
