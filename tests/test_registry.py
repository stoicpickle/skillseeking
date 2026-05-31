from __future__ import annotations

from app.registry import SkillRegistry


def test_registry_lists_seed_skills(seed_skills_dir):
    registry = SkillRegistry.load(seed_skills_dir)

    assert [record.name for record in registry.list_records()] == [
        "compare-claims",
        "extract-claims",
        "source-quality-check",
        "validate-skill-md",
        "write-structured-answer",
    ]
    assert registry.rejections() == []
    extract = registry.get("extract-claims")
    assert extract is not None
    assert extract.source_root == seed_skills_dir.resolve()
    assert not extract.lifecycle.temporary


def test_registry_records_rejections(fixture_skills_dir):
    registry = SkillRegistry.load(fixture_skills_dir)

    assert [record.name for record in registry.list_records()] == ["valid-skill"]
    rejected_names = {rejection.name for rejection in registry.rejections()}
    assert "extra-field-skill" in rejected_names
    assert "malicious-body" in rejected_names
    assert "network-skill" in rejected_names
