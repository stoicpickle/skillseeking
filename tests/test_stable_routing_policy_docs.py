from __future__ import annotations

from pathlib import Path


def test_stable_routing_policy_documents_v1_deferral(repo_root: Path):
    policy = (repo_root / "docs" / "stable-routing-policy.md").read_text(
        encoding="utf-8"
    )
    tasking = (repo_root / "docs" / "internal" / "v1-release-tasking.md").read_text(
        encoding="utf-8"
    )
    contract = (repo_root / "docs" / "v1-release-contract.md").read_text(
        encoding="utf-8"
    )

    assert "Status: v1 deferred" in policy
    assert "Stable routing is not enabled for the v1 local CLI release." in policy
    assert "`stable_routing_enabled` must remain `false`" in policy
    assert "`stable_routing_policy` must remain `stable_routing_unchanged`" in policy
    assert "Positive stable routing is post-v1 work." in policy
    assert "stable-routing policy row" in policy
    assert "stable_routing_policy=deferred_for_v1" in policy

    assert "Status: complete for v1 as deferred/disabled" in tasking
    assert "docs/stable-routing-policy.md" in tasking
    assert "stable routing policy is deferred for v1" in contract
