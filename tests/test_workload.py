import pytest

from auto_eval.authoring import CaseSource
from auto_eval.derive import derive
from auto_eval.gaps import analyze
from auto_eval.prompts import build_ground_truth_message
from auto_eval.render import render_markdown
from auto_eval.runner import run_suite
from auto_eval.schema import (
    Measurement,
    Readiness,
    TaskContext,
    TaskSpec,
    Workload,
    WorkloadMetric,
)
from auto_eval.suite import build, verify_digest
from auto_eval.surface import behaviours_for
from auto_eval.verify import VerifierKind


def news_workload():
    return Workload(
        description="Find recent news articles for a news web app",
        representative_inputs=["Find today's California housing news"],
        data_characteristics=["English articles published in the last 24 hours"],
        request_mix=["80% topic searches; 20% named entities"],
        metrics=[
            WorkloadMetric(
                name="Daily searches",
                kind="volume",
                value="about 10k requests/day",
                role="expected",
            ),
            WorkloadMetric(
                name="p95 latency", kind="latency", value="under 500 ms", role="target"
            ),
            WorkloadMetric(
                name="Monthly spend",
                kind="cost",
                value="under $100/month",
                role="target",
            ),
        ],
    )


def test_old_specs_load_without_inventing_workload(sparse_spec):
    data = sparse_spec.model_dump(exclude={"context", "workload"})
    spec = TaskSpec.model_validate(data)
    assert spec.context == TaskContext()
    assert spec.workload == Workload()
    result = analyze(spec)
    fields = {q.field for q in result.open_questions}
    assert {
        "context.overall_task",
        "context.comparison_task",
        "workload.representative_inputs",
        "workload.metrics",
    } <= fields
    assert result.readiness is Readiness.NEEDS_INPUT


def test_workload_round_trip_and_source_discovery(full_spec):
    full_spec.context = TaskContext(
        overall_task="Make a news web app",
        comparison_task="Choose a news search API",
        preferences=["Prefer low cost over a small latency improvement"],
        details=["Small team"],
    )
    full_spec.workload = news_workload()
    restored = TaskSpec.model_validate_json(full_spec.model_dump_json())
    assert restored == full_spec
    for text in (build_ground_truth_message(restored), render_markdown(restored)):
        for value in (
            "Make a news web app",
            "Choose a news search API",
            "about 10k requests/day",
            "under $100/month",
            "80% topic searches",
            "Small team",
            "Prefer low cost",
        ):
            assert value in text
    assert not any(
        q.field.startswith(("workload.", "context."))
        for q in analyze(restored).open_questions
    )


@pytest.mark.parametrize("role", ["expected", "observed"])
def test_forecasts_and_observations_do_not_become_targets(sparse_spec, role):
    sparse_spec.workload.metrics = [
        WorkloadMetric(name="Latency", kind="latency", value="about 300 ms", role=role)
    ]
    result = derive(sparse_spec)
    assert all(k.target is None for k in result.kpis)
    assert all(k.name != "Latency" for k in result.kpis)


def test_explicit_targets_are_preserved_and_derivation_is_idempotent(sparse_spec):
    sparse_spec.workload = news_workload()
    result = derive(sparse_spec)
    assert {k.name: k.target for k in result.kpis} == {
        "p95 latency": "under 500 ms",
        "Monthly spend": "under $100/month",
    }
    assert all(k.measurement is Measurement.TELEMETRY for k in result.kpis)
    assert derive(result) == result
    assert sparse_spec.kpis == []


def test_existing_explicit_kpi_target_is_not_overwritten(full_spec):
    full_spec.workload.metrics = [
        WorkloadMetric(
            name=full_spec.kpis[0].name,
            kind="latency",
            value="a conflicting requirement",
            role="target",
        )
    ]
    result = derive(full_spec)
    assert len(result.kpis) == 1
    assert result.kpis[0].target == ">= 95%"
    assert any("different targets" in q.why for q in analyze(full_spec).open_questions)


def test_comparison_task_defines_fallback_scope(sparse_spec):
    sparse_spec.context = TaskContext(
        overall_task="Make a news web app", comparison_task="Retrieve fresh articles"
    )
    assert behaviours_for(sparse_spec) == ["Retrieve fresh articles"]
    sparse_spec.subject.in_scope = ["Entity searches"]
    assert behaviours_for(sparse_spec) == ["Entity searches"]


def test_workload_changes_cases_and_survives_run_reporting(agent_spec):
    baseline = build(agent_spec)
    agent_spec.context = TaskContext(
        overall_task="Build a support app",
        comparison_task="Handle refund requests",
        preferences=["Concise replies"],
    )
    agent_spec.workload = Workload(
        representative_inputs=["Refund order 123, which arrived broken."],
        metrics=[
            WorkloadMetric(
                name="Monthly spend",
                kind="cost",
                value="under $100/month",
                role="target",
            )
        ],
    )
    suite = build(agent_spec)
    assert suite.digest != baseline.digest
    assert build(agent_spec).model_dump() == suite.model_dump()
    assert verify_digest(suite)
    examples = [c for c in suite.cases if c.family == "capability.workload_input"]
    assert len(examples) == 1
    assert examples[0].instruction.endswith("Refund order 123, which arrived broken.")
    assert "Build a support app" in examples[0].instruction
    assert examples[0].source is CaseSource.SYNTHESISED
    # Existing incidents/public cases are not rewritten to fit a new workload.
    assert [
        (c.id, c.instruction)
        for c in baseline.cases
        if c.source is not CaseSource.SYNTHESISED
    ] == [
        (c.id, c.instruction)
        for c in suite.cases
        if c.source is not CaseSource.SYNTHESISED
    ]
    run = run_suite(suite, mock=True, samples=1)
    assert any("Build a support app" in note for note in run.report.notes)
    targets = [
        b
        for c in run.report.cases
        for b in c.blocked
        if b.kind is VerifierKind.WORKLOAD_TARGET
    ]
    assert targets
    assert all("aggregate measurements" in b.reason for b in targets)
    assert suite.profile.budget == baseline.profile.budget
