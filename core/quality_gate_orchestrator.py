from copy import deepcopy

from core.publishing_quality import evaluate_publish_source
from core.publishing_repair import repair_publish_source
from core.publishing_structure import evaluate_publish_structure


def _merge_repaired_source(source_payload: dict, repaired_source: dict) -> dict:
    merged = deepcopy(source_payload)
    for field in ("title", "content"):
        value = repaired_source.get(field)
        if isinstance(value, str) and value.strip():
            merged[field] = value
    return merged


def _build_publishable_result(*, final_source: dict, gate_reports: dict, attempted_repair: bool) -> dict:
    return {
        "status": "publishable",
        "attempted_repair": attempted_repair,
        "final_source": final_source,
        "gate_reports": gate_reports,
        "errors": [],
        "repair_summary": {
            "status": "applied" if attempted_repair else "not_needed",
            "reason": "",
        },
    }


def _build_hard_fail_result(
    *,
    final_source: dict,
    gate_reports: dict,
    attempted_repair: bool,
    reason: str,
) -> dict:
    errors: list[str] = []
    for stage in ("rules", "structure"):
        report = gate_reports.get(stage) or {}
        for item in report.get("errors", []):
            text = str(item)
            if text not in errors:
                errors.append(text)
    if reason and reason not in errors:
        errors.append(reason)
    return {
        "status": "hard_fail",
        "attempted_repair": attempted_repair,
        "final_source": final_source,
        "gate_reports": gate_reports,
        "errors": errors,
        "repair_summary": {
            "status": "attempted" if attempted_repair else "skipped",
            "reason": reason,
        },
    }


def _is_immediate_hard_fail(report: dict) -> bool:
    return str(report.get("status", "")).strip() == "hard_fail"


def _needs_repair(*, rules_report: dict, structure_report: dict) -> bool:
    return any(
        str(report.get("status", "")).strip() == "retry_possible"
        for report in (rules_report, structure_report)
    )


def _passes_gate(report: dict) -> bool:
    return str(report.get("status", "")).strip() in {"passed", "publishable"}


def _evaluate_reports(source_payload: dict) -> dict:
    rules_report = evaluate_publish_source(source_payload)
    structure_report = evaluate_publish_structure(source_payload)
    return {
        "rules": rules_report,
        "structure": structure_report,
    }


def evaluate_quality_gate(source_payload: dict, *, repair_enabled: bool = True) -> dict:
    initial_source = deepcopy(source_payload)
    gate_reports = _evaluate_reports(initial_source)
    rules_report = gate_reports["rules"]
    structure_report = gate_reports["structure"]

    if _is_immediate_hard_fail(rules_report) or _is_immediate_hard_fail(structure_report):
        return _build_hard_fail_result(
            final_source=initial_source,
            gate_reports={"initial": gate_reports},
            attempted_repair=False,
            reason="initial hard fail",
        )

    if _passes_gate(rules_report) and _passes_gate(structure_report):
        return _build_publishable_result(
            final_source=initial_source,
            gate_reports={"initial": gate_reports},
            attempted_repair=False,
        )

    if not repair_enabled or not _needs_repair(rules_report=rules_report, structure_report=structure_report):
        return _build_hard_fail_result(
            final_source=initial_source,
            gate_reports={"initial": gate_reports},
            attempted_repair=False,
            reason="repair disabled or not recoverable",
        )

    repaired_patch = repair_publish_source(initial_source, gate_reports)
    final_source = _merge_repaired_source(initial_source, repaired_patch)
    repaired_reports = _evaluate_reports(final_source)
    if _passes_gate(repaired_reports["rules"]) and _passes_gate(repaired_reports["structure"]):
        return _build_publishable_result(
            final_source=final_source,
            gate_reports={"initial": gate_reports, "final": repaired_reports},
            attempted_repair=True,
        )

    return _build_hard_fail_result(
        final_source=final_source,
        gate_reports={"initial": gate_reports, "final": repaired_reports},
        attempted_repair=True,
        reason="repair did not produce publishable source",
    )
