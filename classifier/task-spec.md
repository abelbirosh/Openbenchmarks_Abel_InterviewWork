# The task spec

`TaskSpec` is the contract between the input classifier and everything
downstream. One free-form request in, one `TaskSpec` out. Print the machine
readable version with `auto-eval schema`.

It records the user's goal, workload, comparison and evidence, plus what remains unknown.

## User task and workload — `context`, `workload`

`context.overall_task` is the broader goal, such as making a news web app.
`context.comparison_task` is the decision being evaluated, such as choosing a
news search API for low cost and latency. They may be the same task; neither is
guessed from the other. The `subject` remains the component under test.
`context.preferences` captures soft tradeoffs; `context.details` holds other
relevant information. Hard requirements remain in `constraints`.

`workload` describes the actual data: `description`, `representative_inputs`,
`data_characteristics`, `request_mix`, `metrics` and `notes`. A metric has:

| Field | Meaning |
| --- | --- |
| `name` | The quantity and statistic, such as p95 latency or monthly spend. |
| `kind` | `volume`, `latency`, `cost`, `throughput`, `concurrency`, `input_size`, `output_size`, `other`. |
| `value` | Original units, time basis and uncertainty: `about 10k requests/day`, `p95 under 500 ms`, `under $100/month`. |
| `role` | `expected` forecast, `observed` measurement, or `target` acceptance requirement. |

Values stay textual to preserve ranges, units and uncertainty. No silent unit
conversion, monthly-cost projection, or invented traffic figures. Explicit
latency, cost and throughput targets become telemetry KPIs; forecasts and
observations do not. Existing KPI targets win on a same-name conflict, which
also produces a clarification question.

The workload reaches source discovery and dataset assessment prompts, the
rendered spec, suite notes and run reports. The comparison task supplies the
coverage row when explicit scope is absent. Representative inputs become
concrete capability cases with no invented gold answer; other synthetic cases
receive workload context. Recorded and public case instructions are preserved.

Boards accept the spec with `auto-eval board items.jsonl -c cohort.json -s task.json`;
the web flow passes it automatically. The board stores it and discloses the
actual execution concurrency separately from the expected production load.
Datasets still need to be supplied; request-mix weights are not automatically
sampled or replayed. Aggregate workload targets are not scored by boards, and
agent runs report them as blocked rather than treating a safety budget as an
acceptance test. This is workload-aware benchmark preparation, not a load-test
scheduler or a production cost forecast.

Old specs still load with empty context and workload fields. See
[`examples/spec-news-workload.json`](../examples/spec-news-workload.json).

## 1. What are we testing — `subject`

| Field | Meaning |
| --- | --- |
| `name` | Short name for the thing under test. |
| `kind` | `prompt`, `agent`, `rag_pipeline`, `model`, `tool`, `workflow`, `api_endpoint`, `classifier`, `dataset`, `other`. |
| `description` | A sentence or two on what it does. |
| `interface` | How it is invoked — CLI command, endpoint, function, prompt template. Missing invocation is a non-blocking spec question; execution has its own gate. |
| `inputs` / `outputs` | What goes in, what comes out. |
| `in_scope` / `out_of_scope` | The boundary of this evaluation. |

`eval_types` sits alongside it and says *why* we are evaluating — `capability`,
`regression`, `comparative`, `safety`, `robustness`, `performance`, `cost`,
`compliance`. A task is often several at once.

## 2. KPIs — `kpis`

Each KPI is one thing we will measure. Quantitative and qualitative KPIs use the
same record; `kind` distinguishes them.

| Field | Meaning |
| --- | --- |
| `name` | What it is called. |
| `kind` | `quantitative` (a number) or `qualitative` (a judged quality). |
| `definition` | Precise enough to implement without a follow-up question. |
| `measurement` | `programmatic`, `execution`, `llm_judge`, `human_review`, `telemetry`, or `unknown`. |
| `direction` | `maximize`, `minimize`, `target_range`. |
| `unit` | `%`, `ms`, `USD`, `1-5`. |
| `target` | The pass threshold, verbatim from the user where given. |
| `baseline` | Where it stands today. |
| `priority` | `primary` (the task succeeds or fails on it), `secondary`, or `guardrail` (must not regress). |
| `source` | `stated` by the user, or `inferred` by the classifier. |

The classifier may propose an `inferred` KPI when the task obviously implies one,
but never marks an inferred KPI `primary` — what the task is *for* is the user's
call, not the model's. Every inference also lands in `assumptions`.

`ground_truth` records whether we can tell right from wrong without a human:
what the labels are, where they come from, how many there are.

## 3. Evidence — `evidence`

Documentation, specs, datasets, existing evals, and above all **successful runs**
and **failure cases**. Each item has a `kind`, a `reference` in the user's own
words, an optional `location`, and a `status`:

- `provided` — the content is in hand and can be used now.
- `mentioned_not_provided` — referenced but not attached. This is a fetch, not an
  unknown, and it becomes a specific "can you share X" question.
- `absent` — the user says it does not exist. Does not count as available.

## What the spec could not answer

- `assumptions` — everything the classifier filled in that the user did not say,
  phrased so it can be contradicted in one sentence.
- `open_questions` — what we need back. Each carries the `field` it would fill,
  a `why`, and a `blocking` flag.
- `confidence` — per section, how much came from the user (1.0) rather than from
  inference (0.0).
- `readiness` — `ready`, `needs_input`, or `insufficient`.

## Where readiness comes from

The model extracts; it does not decide. `auto_eval.gaps` recomputes
`open_questions` and `readiness` from rules after every classification, and the
model's own guess is discarded.

`derive.py` runs first: it supplies a default KPI from the evaluation type or
subject when none was given, defaults unknown measurement methods from metric
kind, picks the first stated KPI as primary (otherwise the first KPI), and
defaults an absent evaluation type to capability. These choices are recorded
in assumptions. Explicit workload targets are added before KPI defaults.

**Missing subject blocks:** both its name and description are blank. A raw spec
without KPIs also has a blocking rule, but normal analysis derives a KPI first.

Everything else produces a normal question and the spec reads `needs_input` — a
missing entry point, no ground truth behind a programmatic KPI, no primary KPI,
an untargeted KPI, a judged quality with no anchoring examples, missing docs,
missing successful runs, missing failure cases, evidence referenced but not
supplied. These are all worth chasing, but none of them stops a spec from being
written and reviewed.

Missing overall task, comparison task, typical input, data mix, traffic scale
and preferences also produce non-blocking questions. Any blocking question
means `insufficient`; only non-blocking questions means `needs_input`; no
questions means `ready`. Model-supplied blocking flags are discarded.

Two rules fire on *every* spec that lacks them, because they are what separates
an anchored eval from a guessed one: ask for documentation, and ask for examples
of runs that came out the way the user wanted.

Model questions are merged in after the rules and deduplicated against them by
token overlap, so a reworded echo of a rule question is dropped and a genuinely
new question survives.

## A note on required fields

The spec is extracted through OpenAI structured outputs in strict mode, which
makes every property required. The model therefore returns all top-level
fields on every call, emitting empty lists and nulls for what it did not find,
rather than omitting them. An empty `kpis` means "found nothing"; deterministic
derivation then proposes a default instead of inventing a user-stated metric.
