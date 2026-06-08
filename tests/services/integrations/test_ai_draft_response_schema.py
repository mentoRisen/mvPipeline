"""Regression tests for OpenAI strict JSON Schema compliance."""

from __future__ import annotations

import json

from app.services.integrations.ai_draft_response_schema import draft_bundle_json_schema


def _collect_strict_object_issues(node: object, path: str = "") -> list[str]:
    """OpenAI strict JSON Schema: all property keys must be listed in required."""
    issues: list[str] = []
    if not isinstance(node, dict):
        return issues
    if node.get("type") == "object" and "properties" in node:
        props = node.get("properties")
        required = node.get("required")
        if isinstance(props, dict):
            prop_keys = set(props.keys())
            req_keys = set(required) if isinstance(required, list) else set()
            missing = prop_keys - req_keys
            extra = req_keys - prop_keys
            if missing:
                issues.append(f"{path or 'root'}: missing from required: {sorted(missing)}")
            if extra:
                issues.append(f"{path or 'root'}: required but not in properties: {sorted(extra)}")
        ap = node.get("additionalProperties")
        if ap is not False:
            issues.append(f"{path or 'root'}: additionalProperties must be false (got {ap!r})")
    for key, value in node.items():
        if key in ("properties", "required", "additionalProperties"):
            continue
        child_path = f"{path}.{key}" if path else key
        if isinstance(value, dict):
            issues.extend(_collect_strict_object_issues(value, child_path))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    issues.extend(
                        _collect_strict_object_issues(item, f"{child_path}[{i}]")
                    )
    return issues


def _collect_additional_properties_flags(node: object, path: str = "") -> list[tuple[str, bool]]:
    """Walk schema; return paths where additionalProperties is not explicitly false."""
    issues: list[tuple[str, bool]] = []
    if not isinstance(node, dict):
        return issues
    if node.get("type") == "object":
        ap = node.get("additionalProperties")
        if ap is not False:
            issues.append((path or "root", ap))
    for key, value in node.items():
        if key == "additionalProperties":
            continue
        child_path = f"{path}.{key}" if path else key
        if isinstance(value, dict):
            issues.extend(_collect_additional_properties_flags(value, child_path))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    issues.extend(
                        _collect_additional_properties_flags(item, f"{child_path}[{i}]")
                    )
    return issues


def test_draft_bundle_schema_sets_task_and_job_caps() -> None:
    fmt = draft_bundle_json_schema(max_items=2, max_jobs=4)
    schema = fmt["json_schema"]["schema"]
    items = schema["properties"]["items"]
    assert items["maxItems"] == 2
    item_props = items["items"]["properties"]["jobs"]
    assert item_props["maxItems"] == 4


def test_draft_bundle_schema_is_openai_strict_compliant() -> None:
    fmt = draft_bundle_json_schema(max_items=3, max_jobs=2)
    schema = fmt["json_schema"]["schema"]
    assert fmt["json_schema"]["strict"] is True

    issues = _collect_strict_object_issues(schema)
    assert issues == [], f"strict schema violations: {issues}"

    bad = _collect_additional_properties_flags(schema)
    assert bad == [], f"additionalProperties must be false on all objects: {bad}"


def test_draft_bundle_schema_includes_instagram_post_fields() -> None:
    fmt = draft_bundle_json_schema(max_items=1, max_jobs=1)
    raw = json.dumps(fmt)
    assert '"theme"' in raw
    assert '"caption"' in raw
    assert '"prompt"' in raw


def test_draft_bundle_schema_pins_template_to_instagram_post() -> None:
    fmt = draft_bundle_json_schema(max_items=1, max_jobs=1)
    task = (
        fmt["json_schema"]["schema"]["properties"]["items"]["items"]["properties"]["task"]
    )
    assert task["properties"]["template"] == {
        "type": "string",
        "enum": ["instagram_post"],
    }


def _draft_job_one_of(fmt: dict) -> list[dict]:
    job_items = (
        fmt["json_schema"]["schema"]["properties"]["items"]["items"]["properties"]["jobs"][
            "items"
        ]
    )
    return job_items["oneOf"]


def test_draft_bundle_schema_pins_job_generators() -> None:
    fmt = draft_bundle_json_schema(max_items=1, max_jobs=1)
    branches = _draft_job_one_of(fmt)
    image_branch = next(b for b in branches if "dalle" in b["properties"]["generator"]["enum"])
    runway_branch = next(
        b for b in branches if b["properties"]["generator"]["enum"] == ["runway-video"]
    )
    assert image_branch["properties"]["generator"] == {
        "type": "string",
        "enum": ["dalle", "gptimage15", "gptimage2"],
    }
    assert runway_branch["properties"]["generator"] == {
        "type": "string",
        "enum": ["runway-video"],
    }


def test_draft_bundle_schema_pins_job_purpose() -> None:
    fmt = draft_bundle_json_schema(max_items=1, max_jobs=1)
    branches = _draft_job_one_of(fmt)
    image_branch = next(b for b in branches if "imagecontent" in b["properties"]["purpose"]["enum"])
    runway_branch = next(
        b for b in branches if b["properties"]["purpose"]["enum"] == ["videocontent"]
    )
    assert image_branch["properties"]["purpose"] == {
        "type": "string",
        "enum": ["imagecontent"],
    }
    assert runway_branch["properties"]["purpose"] == {
        "type": "string",
        "enum": ["videocontent"],
    }


def test_draft_bundle_schema_requires_job_reference_id() -> None:
    fmt = draft_bundle_json_schema(max_items=1, max_jobs=1)
    for branch in _draft_job_one_of(fmt):
        assert "reference_id" in branch["properties"]
        assert "reference_id" in branch["required"]
        assert branch["properties"]["reference_id"] == {
            "type": "integer",
            "minimum": 1,
        }


def test_draft_bundle_schema_runway_prompt_requires_all_keys() -> None:
    fmt = draft_bundle_json_schema(max_items=1, max_jobs=1)
    runway_branch = next(
        b
        for b in _draft_job_one_of(fmt)
        if b["properties"]["generator"]["enum"] == ["runway-video"]
    )
    prompt_schema = runway_branch["properties"]["prompt"]
    assert set(prompt_schema["required"]) == {"prompt", "model", "reference_id"}
    assert prompt_schema["properties"]["model"]["enum"] == [
        "gen4_turbo",
        "veo3.1_fast",
    ]
