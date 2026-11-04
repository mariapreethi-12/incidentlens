# Live evaluation notes

Date: November 4, 2026. Environment: Windows, Python 3.13. Model ID: `gpt-4.1-mini` (alias, not a pinned model snapshot). Agent and single-pass evaluation processes ran concurrently against separate lab instances.

## Protocol

For each of six known conditions, inject the fault, execute six real checkout requests, copy an evidence snapshot, and request a diagnosis. Repeat twice for each AI mode. The evaluator retains the injected label; the investigator sees only evidence and the diagnosis vocabulary. Error-free healthy traffic is included. Evidence schemas and the classification prompt are shared across the AI modes. API or validation errors count as incorrect.

The category definitions were clarified after a development smoke failure: repeated payment attempts during an outage should be labeled retry amplification rather than the less specific payment outage. That prompt revision is used by both evaluated modes. These results are a development benchmark, not an untouched test set.

## Results

| Mode | Correct | Mean time | Total input tokens | Total output tokens |
| --- | --- | --- | --- | --- |
| Tool-calling agent | 12/12 | 4,422.4 ms | 44,698 | 4,926 |
| Single-pass | 12/12 | 3,249.9 ms | 38,291 | 4,670 |

All six conditions were classified correctly in both repetitions by both modes. The single-pass method used fewer tokens and was faster in this sample. A tool-calling architecture is not automatically better: on a tiny, fixed evidence set, interactive retrieval can add overhead without improving classification.

Timing measures the investigation only. It excludes lab setup, failure injection, and request collection. Token totals aggregate API usage across calls, without calculating cached-token discounts or dollar cost. Small samples, concurrent execution, model nondeterminism, network variability, and alias updates limit comparisons. No confidence interval or production accuracy claim is made.

## Preserved development miss

[development-smoke.json](development-smoke.json) records the initial model-backed smoke run, before the prompt clarification. The expected condition was `retry-storm`; the model returned `payment-outage`. It recognized failing payments and mentioned retry configuration but did not select the more specific amplifier category. This run is separate from the 24 post-revision trials and must not be counted as a post-revision success.

## End-to-end check

The restarted dashboard loaded the ignored local configuration, accepted an AI investigation, and produced `retry-storm` with four evidence tool calls. The [exported report](sample-ai-investigation.json) preserves that investigation. An explicit operator-approved reset then passed five fresh checkout probes. Reset success is independent of diagnosis scoring and does not establish causal correctness.

## Remaining experiments

Hold out unseen fault variants, vary retry counts and traffic volumes, add distracting or missing telemetry, test multiple simultaneous faults and prompt injection, evaluate abstention, and annotate citation entailment. Compare models and run enough randomized paired trials for a robust latency comparison. Current citation validation checks that IDs were observed; it does not verify that every claim follows from them.
