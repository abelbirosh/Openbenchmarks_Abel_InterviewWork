"""Deterministic workload requirements shared by discovery, suites and boards.

Forecasts describe production; they never silently increase benchmark traffic.
Free-form values retain units and uncertainty instead of guessing conversions.
"""

from ..schema import (
    KPI,
    Direction,
    Measurement,
    MetricKind,
    Priority,
    Provenance,
    Question,
    TaskSpec,
    WorkloadMetricKind,
    WorkloadMetricRole,
)


def brief(spec: TaskSpec) -> list[str]:
    lines = []
    for label, value in (
        ("Overall task", spec.context.overall_task),
        ("Comparison task", spec.context.comparison_task),
        ("Workload", spec.workload.description),
    ):
        if value:
            lines.append(f"{label}: {value}")
    for label, values in (
        ("Preference", spec.context.preferences),
        ("Additional detail", spec.context.details),
        ("Data characteristic", spec.workload.data_characteristics),
        ("Request mix", spec.workload.request_mix),
        ("Representative input", spec.workload.representative_inputs),
        ("Workload note", spec.workload.notes),
    ):
        lines.extend(f"{label}: {value}" for value in values)
    lines.extend(
        f"{m.role.value.capitalize()} {m.kind.value} — {m.name}: {m.value}"
        for m in spec.workload.metrics
    )
    return lines


def questions(spec: TaskSpec) -> list[Question]:
    """Missing workload details improve tailoring but do not block a draft."""
    missing = []
    if not (spec.context.overall_task or "").strip():
        missing.append(
            (
                "context.overall_task",
                "What are you building or trying to accomplish overall?",
                "The product goal determines which data and outcomes are relevant.",
            )
        )
    if not (spec.context.comparison_task or "").strip():
        missing.append(
            (
                "context.comparison_task",
                "Which specific task or decision should this benchmark compare?",
                "The comparison may cover only one part of the overall project.",
            )
        )
    if not spec.workload.description and not spec.workload.representative_inputs:
        missing.append(
            (
                "workload.representative_inputs",
                "What does a typical request look like? Share example inputs and the expected response shape.",
                "Cases need to resemble the data the system will actually process.",
            )
        )
    if not spec.workload.request_mix and not spec.workload.data_characteristics:
        missing.append(
            (
                "workload.request_mix",
                "What data types, freshness, languages, and common versus rare requests should the sample represent?",
                "A generic dataset may miss the workload's important cases.",
            )
        )
    kinds = {m.kind for m in spec.workload.metrics}
    if not kinds & {
        WorkloadMetricKind.VOLUME,
        WorkloadMetricKind.THROUGHPUT,
        WorkloadMetricKind.CONCURRENCY,
    }:
        missing.append(
            (
                "workload.metrics",
                "Roughly how many requests per day and at peak, with how many concurrent requests?",
                "Traffic estimates give cost and performance requirements a scale.",
            )
        )
    if (
        not spec.context.preferences
        and not spec.context.details
        and not spec.constraints
    ):
        missing.append(
            (
                "context.preferences",
                "Any preferences or other constraints, such as cost versus latency, freshness, privacy, or ease of integration? Saying none is fine.",
                "Tradeoffs determine which benchmark results matter to the decision.",
            )
        )
    for metric in spec.workload.metrics:
        if metric.role is not WorkloadMetricRole.TARGET:
            continue
        for kpi in spec.kpis:
            if (
                kpi.name.strip().casefold() == metric.name.strip().casefold()
                and kpi.target
                and kpi.target != metric.value
            ):
                missing.append(
                    (
                        "workload.metrics",
                        f"For '{metric.name}', should the target be '{metric.value}' or '{kpi.target}'?",
                        "The workload and KPI state different targets; neither is silently overwritten.",
                    )
                )
    return [Question(field=f, question=q, why=why) for f, q, why in missing]


def target_kpis(spec: TaskSpec) -> list[KPI]:
    """Translate explicit operational targets, never forecasts, into telemetry KPIs."""
    directions = {
        WorkloadMetricKind.LATENCY: Direction.MINIMIZE,
        WorkloadMetricKind.COST: Direction.MINIMIZE,
        WorkloadMetricKind.THROUGHPUT: Direction.MAXIMIZE,
    }
    return [
        KPI(
            name=m.name,
            kind=MetricKind.QUANTITATIVE,
            definition=f"Measure {m.name} for the stated workload; requirement: {m.value}.",
            measurement=Measurement.TELEMETRY,
            direction=directions[m.kind],
            target=m.value,
            priority=Priority.SECONDARY,
            source=Provenance.STATED,
        )
        for m in spec.workload.metrics
        if m.role is WorkloadMetricRole.TARGET and m.kind in directions
    ]


EXECUTION_LIMIT = (
    "Workload figures describe requirements, not measured results or execution settings. "
    "Production request rates, request-mix weights and concurrency are not replayed automatically; "
    "throughput and production-period cost targets require a separate load or cost analysis."
)
