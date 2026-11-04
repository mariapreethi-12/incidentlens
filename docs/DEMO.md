# A one-minute demo

1. Start the app with `python -m incidentlens.server`.
2. Select **Retry amplification**, then inject and collect traffic.
3. Point out eight checkout requests versus thirty-two failing payment requests.
4. Choose **AI agent · tool calling** and run the investigation. The saved local configuration is loaded at server startup.
5. Expand `read_traces` and show four payment attempts sharing the same checkout trace ID.
6. Click a citation to inspect its observed record.
7. Approve the lab reset. Show five fresh checkouts passing verification.
8. Export the JSON report.

Do not call a baseline recording an AI agent recording. For the AI version, show model identity, tool usage, token usage, and an actual successful model-backed run.

## LinkedIn draft for the evaluated version

I built IncidentLens, a local lab for evidence-driven incident investigation.

The checkout app can fail in five controlled ways: a database lock, a payment outage, slow inventory, a checkout regression, and retry amplification. These produce actual HTTP responses, SQLite failures and measured request traces.

The investigation interface exposes the evidence behind a diagnosis and requires an operator to approve recovery. Five fresh checkouts verify the result.

I compared a tool-calling AI investigator against the same evidence in a single prompt, using GPT-4.1 mini. Both classified 12/12 controlled trials correctly. The single-prompt version was faster (3.25 vs. 4.42 seconds on average) and used fewer tokens.

One useful failure: the initial agent confused retry amplification with a simple payment outage. I clarified the category definitions, reran the tests, and preserved that original miss in the repository. These are small, known lab scenarios, not a claim about production accuracy.

Repository: https://github.com/mariapreethi-12/incidentlens

[Add a short recording of a live AI investigation. OpenAI's model was used in these evaluations; tag providers only when discussing technology actually used.]

## Ownership and development

Present the project under your name and account. Understand the architecture, reproduce the measurements, and explain the tradeoffs. Describe AI development assistance honestly when relevant. Keep commit history factual; do not fabricate historical development dates or performance claims.
