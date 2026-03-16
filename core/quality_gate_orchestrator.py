from copy import deepcopy

from core.publishing_critic import evaluate_publish_critic
from core.publishing_quality import evaluate_publish_source
from core.publishing_regenerate import regenerate_publish_source
from core.publishing_repair import repair_publish_source
from core.publishing_structure import evaluate_publish_structure


def _merge_repaired_source(source_payload: dict, repaired_source: dict) -> dict:
    merged = deepcopy(source_payload)
    for field in ("title", "content"):
        value = repaired_source.get(field)
        if isinstance(value, str) and value.strip():
            merged[field] = value
    return merged


def _normalize_result_source(source_payload: dict) -> dict:
    normalized: dict = {}
    for key, value in deepcopy(source_payload).items():
        if hasattr(value, "__fspath__"):
            normalized[key] = str(value)
        else:
            normalized[key] = value
    return normalized


def _default_regeneration_summary(*, attempted_regenerate: bool, status: str = "skipped", reason: str = "") -> dict:
    if not attempted_regenerate:
        return {
            "status": "skipped",
            "reason": "",
        }
    return {
        "status": status,
        "reason": reason,
    }


def _build_publishable_result(
    *,
    final_source: dict,
    gate_reports: dict,
    attempted_repair: bool,
    attempted_regenerate: bool = False,
    regeneration_summary: dict | None = None,
) -> dict:
    return {
        "status": "publishable",
        "attempted_repair": attempted_repair,
        "attempted_regenerate": attempted_regenerate,
        "final_source": _normalize_result_source(final_source),
        "gate_reports": gate_reports,
        "errors": [],
        "repair_summary": {
            "status": "applied" if attempted_repair else "not_needed",
            "reason": "",
        },
        "regeneration_summary": regeneration_summary
        or _default_regeneration_summary(attempted_regenerate=attempted_regenerate),
    }


def _build_hard_fail_result(
    *,
    final_source: dict,
    gate_reports: dict,
    attempted_repair: bool,
    reason: str,
    attempted_regenerate: bool = False,
    regeneration_summary: dict | None = None,
) -> dict:
    errors: list[str] = []
    for report_bundle in gate_reports.values():
        if not isinstance(report_bundle, dict):
            continue
        for stage in ("rules", "structure", "critic"):
            report = report_bundle.get(stage) or {}
            for item in report.get("errors", []) if isinstance(report, dict) else []:
                text = str(item)
                if text not in errors:
                    errors.append(text)
            for item in report.get("issues", []) if isinstance(report, dict) else []:
                text = str(item)
                if text not in errors:
                    errors.append(text)
    if reason and reason not in errors:
        errors.append(reason)
    return {
        "status": "hard_fail",
        "attempted_repair": attempted_repair,
        "attempted_regenerate": attempted_regenerate,
        "final_source": _normalize_result_source(final_source),
        "gate_reports": gate_reports,
        "errors": errors,
        "repair_summary": {
            "status": "attempted" if attempted_repair else "skipped",
            "reason": reason,
        },
        "regeneration_summary": regeneration_summary
        or _default_regeneration_summary(attempted_regenerate=attempted_regenerate),
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


def _with_critic_report(*, gate_reports: dict, critic_report: dict, repaired: bool) -> dict:
    bundled = deepcopy(gate_reports)
    if repaired:
        bundled.setdefault("final", {})
        bundled["final"]["critic"] = critic_report
        return bundled

    initial_reports = deepcopy(gate_reports.get("initial", {}))
    initial_reports["critic"] = critic_report
    bundled["final"] = initial_reports
    return bundled


def _with_final_report(*, gate_reports: dict, final_reports: dict, key: str | None = None) -> dict:
    bundled = deepcopy(gate_reports)
    bundled["final"] = deepcopy(final_reports)
    if key:
        bundled[key] = deepcopy(final_reports)
    return bundled


def _is_regenerateable_structure_failure(report: dict) -> bool:
    if str(report.get("status", "")).strip() != "hard_fail":
        return False
    markers = (
        "missing meaningful event progression",
        "weak or absent conflict/change signal",
        "scene outcome is structurally empty",
    )
    for item in report.get("errors", []) if isinstance(report, dict) else []:
        text = str(item).strip().lower()
        if any(marker in text for marker in markers):
            return True
    return False


def _is_regenerateable_failure(*, rules_report: dict, structure_report: dict, critic_report: dict | None = None) -> bool:
    if isinstance(critic_report, dict) and str(critic_report.get("status", "")).strip() == "blocked":
        return True
    return _is_regenerateable_structure_failure(rules_report) or _is_regenerateable_structure_failure(structure_report)


def _merge_regenerated_source(source_payload: dict, regenerated_source: dict) -> dict:
    return _merge_repaired_source(source_payload, regenerated_source)


def _attempt_regeneration(
    source_payload: dict,
    *,
    episode_plan: dict | None,
    regenerate_fn,
) -> tuple[dict | None, dict]:
    applied_regenerate_fn = regenerate_fn or regenerate_publish_source
    regeneration_result = applied_regenerate_fn(
        deepcopy(source_payload),
        episode_plan=deepcopy(episode_plan) if isinstance(episode_plan, dict) else episode_plan,
        project_name=source_payload.get("project_name"),
        length_goal=(episode_plan or {}).get("target_length") if isinstance(episode_plan, dict) else None,
    )
    status = str(regeneration_result.get("status", "")).strip() or "failed"
    reason = str(regeneration_result.get("reason", "")).strip()
    summary_text = str(regeneration_result.get("regeneration_summary", "")).strip()
    regeneration_summary = {
        "status": status,
        "reason": summary_text or reason,
    }
    if status != "applied":
        return None, regeneration_summary
    return _merge_regenerated_source(source_payload, regeneration_result), regeneration_summary


def evaluate_quality_gate(
    source_payload: dict,
    *,
    episode_plan: dict | None = None,
    repair_enabled: bool = True,
    regenerate_enabled: bool = True,
    regenerate_fn=None,
) -> dict:
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
        critic_report = evaluate_publish_critic(initial_source, episode_plan=episode_plan)
        critic_gate_reports = _with_critic_report(
            gate_reports={"initial": gate_reports},
            critic_report=critic_report,
            repaired=False,
        )
        if critic_report.get("status") == "passed":
            return _build_publishable_result(
                final_source=initial_source,
                gate_reports=critic_gate_reports,
                attempted_repair=False,
            )
        if regenerate_enabled and _is_regenerateable_failure(
            rules_report=rules_report,
            structure_report=structure_report,
            critic_report=critic_report,
        ):
            regenerated_source, regeneration_summary = _attempt_regeneration(
                initial_source,
                episode_plan=episode_plan,
                regenerate_fn=regenerate_fn,
            )
            if regenerated_source is None:
                return _build_hard_fail_result(
                    final_source=initial_source,
                    gate_reports=critic_gate_reports,
                    attempted_repair=False,
                    attempted_regenerate=True,
                    regeneration_summary=regeneration_summary,
                    reason=regeneration_summary.get("reason", "") or "regeneration failed",
                )
            regenerated_reports = _evaluate_reports(regenerated_source)
            if _passes_gate(regenerated_reports["rules"]) and _passes_gate(regenerated_reports["structure"]):
                regenerated_critic_report = evaluate_publish_critic(regenerated_source, episode_plan=episode_plan)
                final_reports = _with_critic_report(
                    gate_reports={"initial": regenerated_reports},
                    critic_report=regenerated_critic_report,
                    repaired=False,
                )["final"]
                regenerated_gate_reports = _with_final_report(
                    gate_reports={"initial": gate_reports},
                    final_reports=final_reports,
                    key="regenerated",
                )
                if regenerated_critic_report.get("status") == "passed":
                    return _build_publishable_result(
                        final_source=regenerated_source,
                        gate_reports=regenerated_gate_reports,
                        attempted_repair=False,
                        attempted_regenerate=True,
                        regeneration_summary=regeneration_summary,
                    )
                return _build_hard_fail_result(
                    final_source=regenerated_source,
                    gate_reports=regenerated_gate_reports,
                    attempted_repair=False,
                    attempted_regenerate=True,
                    regeneration_summary=regeneration_summary,
                    reason=str(regenerated_critic_report.get("summary", "")).strip() or "critic blocked publish",
                )
            regenerated_gate_reports = _with_final_report(
                gate_reports={"initial": gate_reports},
                final_reports=regenerated_reports,
                key="regenerated",
            )
            return _build_hard_fail_result(
                final_source=regenerated_source,
                gate_reports=regenerated_gate_reports,
                attempted_repair=False,
                attempted_regenerate=True,
                regeneration_summary=regeneration_summary,
                reason="regenerated source did not produce publishable source",
            )
        return _build_hard_fail_result(
            final_source=initial_source,
            gate_reports=critic_gate_reports,
            attempted_repair=False,
            reason=str(critic_report.get("summary", "")).strip() or "critic blocked publish",
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
        critic_report = evaluate_publish_critic(final_source, episode_plan=episode_plan)
        critic_gate_reports = _with_critic_report(
            gate_reports={"initial": gate_reports, "final": repaired_reports},
            critic_report=critic_report,
            repaired=True,
        )
        if critic_report.get("status") == "passed":
            return _build_publishable_result(
                final_source=final_source,
                gate_reports=critic_gate_reports,
                attempted_repair=True,
            )
        if regenerate_enabled and _is_regenerateable_failure(
            rules_report=repaired_reports["rules"],
            structure_report=repaired_reports["structure"],
            critic_report=critic_report,
        ):
            regenerated_source, regeneration_summary = _attempt_regeneration(
                final_source,
                episode_plan=episode_plan,
                regenerate_fn=regenerate_fn,
            )
            if regenerated_source is None:
                return _build_hard_fail_result(
                    final_source=final_source,
                    gate_reports=critic_gate_reports,
                    attempted_repair=True,
                    attempted_regenerate=True,
                    regeneration_summary=regeneration_summary,
                    reason=regeneration_summary.get("reason", "") or "regeneration failed",
                )
            regenerated_reports = _evaluate_reports(regenerated_source)
            if _passes_gate(regenerated_reports["rules"]) and _passes_gate(regenerated_reports["structure"]):
                regenerated_critic_report = evaluate_publish_critic(regenerated_source, episode_plan=episode_plan)
                final_reports = _with_critic_report(
                    gate_reports={"initial": regenerated_reports},
                    critic_report=regenerated_critic_report,
                    repaired=False,
                )["final"]
                regenerated_gate_reports = _with_final_report(
                    gate_reports={"initial": gate_reports, "final": repaired_reports},
                    final_reports=final_reports,
                    key="regenerated",
                )
                if regenerated_critic_report.get("status") == "passed":
                    return _build_publishable_result(
                        final_source=regenerated_source,
                        gate_reports=regenerated_gate_reports,
                        attempted_repair=True,
                        attempted_regenerate=True,
                        regeneration_summary=regeneration_summary,
                    )
                return _build_hard_fail_result(
                    final_source=regenerated_source,
                    gate_reports=regenerated_gate_reports,
                    attempted_repair=True,
                    attempted_regenerate=True,
                    regeneration_summary=regeneration_summary,
                    reason=str(regenerated_critic_report.get("summary", "")).strip() or "critic blocked publish",
                )
            regenerated_gate_reports = _with_final_report(
                gate_reports={"initial": gate_reports, "final": repaired_reports},
                final_reports=regenerated_reports,
                key="regenerated",
            )
            return _build_hard_fail_result(
                final_source=regenerated_source,
                gate_reports=regenerated_gate_reports,
                attempted_repair=True,
                attempted_regenerate=True,
                regeneration_summary=regeneration_summary,
                reason="regenerated source did not produce publishable source",
            )
        return _build_hard_fail_result(
            final_source=final_source,
            gate_reports=critic_gate_reports,
            attempted_repair=True,
            reason=str(critic_report.get("summary", "")).strip() or "critic blocked publish",
        )

    return _build_hard_fail_result(
        final_source=final_source,
        gate_reports={"initial": gate_reports, "final": repaired_reports},
        attempted_repair=True,
        reason="repair did not produce publishable source",
    )
