from __future__ import annotations

from pathlib import Path

from app.eval_runner import load_eval_suite, run_eval_suite


def test_v1_release_eval_suite_is_the_release_gate(repo_root: Path):
    suite = repo_root / "evals" / "v1_release.jsonl"
    tasks = load_eval_suite(suite)

    ids = [task.id for task in tasks]
    assert len(tasks) == 11
    assert len(ids) == len(set(ids))
    assert "v1_release_stable_routing_policy_deferred_even_when_ready" in ids
    assert all("v1_release" in task.tags for task in tasks)
    assert all("release_gate" in task.tags for task in tasks)

    expected_tags = {
        "happy_path",
        "missing_skill",
        "safety",
        "approval_required",
        "adversarial",
        "temporary_success",
        "repair_required",
        "stable_readiness",
        "stable_routing_policy",
        "duplicate_candidate",
        "negative_evidence",
        "stable_routing_disabled",
    }
    observed_tags = {tag for task in tasks for tag in task.tags}
    assert expected_tags <= observed_tags


def test_v1_release_eval_suite_passes_without_durable_skill_mutation(
    copied_seed_skills,
    repo_root: Path,
    tmp_path,
):
    suite = repo_root / "evals" / "v1_release.jsonl"
    durable_before = _snapshot_tree(copied_seed_skills)

    report = run_eval_suite(suite, copied_seed_skills, tmp_path / "runs")

    assert report["passed"] is True
    assert report["aggregate"]["total"] == 11
    assert report["aggregate"]["failed"] == 0
    assert report["aggregate"]["task_pass_rate"] == 1.0
    assert report["aggregate"]["governor_decision_accuracy"] == 1.0
    assert report["aggregate"]["lifecycle_evidence_accuracy"] == 1.0
    assert report["aggregate"]["stable_readiness_accuracy"] == 1.0
    assert report["aggregate"]["trace_completeness"] == 1.0
    assert report["aggregate"]["failure_categories"] == {}

    dimensions = report["aggregate"]["diagnostic_dimensions"]
    assert dimensions["v1_release"]["total"] == 11
    assert dimensions["release_gate"]["passed"] == 11
    assert dimensions["stable_readiness"]["total"] == 4
    assert dimensions["stable_routing_disabled"]["total"] == 4
    assert dimensions["stable_routing_policy"]["total"] == 1
    assert dimensions["input_focus"]["total"] == 4
    assert dimensions["repair_required"]["total"] == 1
    assert dimensions["duplicate_candidate"]["total"] == 1
    assert dimensions["negative_evidence"]["total"] == 1

    stable_reports = [
        stable_report
        for task in report["tasks"]
        for stable_report in task["stable_readiness_reports"]
    ]
    assert len(stable_reports) == 4
    assert {item["stable_routing_enabled"] for item in stable_reports} == {False}
    assert {item["stable_review_authorized"] for item in stable_reports} == {False}
    assert {item["stable_promotion_authorized"] for item in stable_reports} == {False}
    for task in report["tasks"]:
        if "stable_readiness" not in task["tags"]:
            continue
        assert task["expected"]["stable_review_authorized"] is False
        assert task["expected"]["stable_promotion_authorized"] is False
        assert task["expected"]["stable_routing_enabled"] is False

    assert _snapshot_tree(copied_seed_skills) == durable_before


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
