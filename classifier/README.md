# Classifier

Turns a free-form "can you test this for me" into a structured evaluation task
spec. First stage of the pipeline — everything downstream reads its `TaskSpec`.

It extracts four things and then says what's missing:

1. **What's being tested** — the artifact, how it's invoked, what's in and out of scope.
2. **KPIs** — metrics and qualities that decide success, with thresholds where given.
3. **Evidence** — docs, datasets, successful runs, known failures.
4. **User context and workload** — the overall goal, narrower comparison task,
   representative data, traffic estimates, operational targets and preferences.

Anything the user didn't supply becomes an explicit question rather than a
guess. See [task-spec.md](task-spec.md) for the field-by-field contract.

Once the spec has no blocking questions left, the [ground truth
identifier](../ground_truth/) takes over: it searches for public data and
baselines, then opens each source and says what is behind it.

## Setup

```bash
pip install -e ".[dev,web]"
```

```bash
cp .env.example .env
```

Put your key in `.env` as `OPENAI_API_KEY`. It's gitignored. `CLOSED_BENCH_MODEL`
and `CLOSED_BENCH_BASE_URL` are optional overrides; an exported variable beats the
file.

## Run

```bash
closed-bench serve
```

The UI at <http://127.0.0.1:8000> is the quickest way to try it — paste a
request, hit Classify. The result is a short verdict, with the spec itself one
click down under "Full spec". Each blocking question gets its own box; fill them
all and Submit answers re-classifies the original request with the answers
appended, which is what clears the block. Localhost, no auth; it's a test
harness, not a deployment target.

From the command line:

```bash
closed-bench classify -f examples/request.txt --md task.md --json task.json
```

`classify` exits `0` when the spec is usable and `2` when it has a blocking
question, so a pipeline can gate on it. `closed-bench models` lists what your key
can reach; `closed-bench schema` prints the `TaskSpec` JSON schema.

From Python:

```python
from closed_bench import classify, render_markdown

spec = classify("our summarizer is too verbose and sometimes invents dates")
print(spec.readiness, [q.question for q in spec.open_questions])
```

## How it works

Extraction runs on `gpt-5-mini` via OpenAI structured outputs. Strict mode makes
every field required, so the model returns empty lists rather than omitting
fields — an empty `kpis` means "found nothing".

**The model extracts; it doesn't judge completeness.** `gaps.py` recomputes the
open questions and the readiness verdict from rules after every run and discards
the model's own guess, so that decision is deterministic and testable offline.
That includes the model's view of what blocks: a question it raised always comes
back non-blocking, because left to itself it calls "send me your transcripts" a
showstopper and the pipeline never moves.

**Blocking is a last resort; the rest is derived.** `derive.py` runs first and
fills in what the request implies — a KPI when none was named, a grading method
from the metric's kind, which KPI is primary, what sort of evaluation this is.
Each value is marked `inferred` and recorded in `assumptions`, and `gaps.py`
still asks about it as a normal question, so it is a starting point to correct
rather than a claim about what you said. What's left that can block is a request
that never says what is under test — there is nothing to point an eval at, and
no default will do. Everything else reads `needs_input` and proceeds.

The derived KPI follows what you told us: an eval type you named wins (`safety` →
violation rate, `performance` → p95 latency, `cost` → cost per run), then the
kind of subject (`classifier` → accuracy, `rag_pipeline` → answer faithfulness),
falling back to task success rate.

Two rules fire on every spec that lacks them: ask for documentation, and ask for
examples of runs that came out the way the user wanted. Those are what separate
an anchored eval from a guessed one.

The request is treated as data — text inside it addressed to the classifier gets
classified, not obeyed.

## Layout

| Path | What's in it |
| --- | --- |
| [schema.py](../closed_bench/schema/__init__.py) | `TaskSpec` — the contract everything downstream reads. |
| [prompts.py](../closed_bench/prompts/__init__.py) | The extraction system prompt. |
| [classifier.py](../closed_bench/classifier/__init__.py) | The API call, error mapping, input limits. |
| [derive.py](../closed_bench/derive/__init__.py) | Fills the holes the spec implies, before any question is asked. |
| [benchmarks.py](../closed_bench/benchmarks/__init__.py) | Ten real public benchmarks, matched onto a spec offline. |
| [gaps.py](../closed_bench/gaps/__init__.py) | Rule-based gap analysis and the readiness verdict. |
| [render.py](../closed_bench/render/__init__.py) | `TaskSpec` → task document. |
| [config.py](../closed_bench/config/__init__.py) | `.env` loading and provider settings. |
| [cli.py](../closed_bench/cli/__init__.py) · [web.py](../closed_bench/web/__init__.py) | The `closed-bench` command and the web UI. |

## Tests

```bash
pytest
```

119 tests, all offline — the classifier and web tests drive fakes, the gap and
render layers are pure functions. No test spends money.
