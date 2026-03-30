"""
Evaluator for determining if skills are properly used by the agent.

Test cases are loaded from use_cases.yaml files co-located with each skill.
Each query is tested to ensure the owning skill is called by the agent.

Requires ANTHROPIC_API_KEY to be set in the environment.

Run with:
    uv run pytest tests/test_skill_selection_accuracy.py -v
"""

import asyncio
from pathlib import Path
from typing import TypedDict

import anthropic
import frontmatter  # type: ignore[import-untyped]
import pytest
import yaml
from llm_client import (
    HAIKU_MODEL,
    MAX_ATTEMPTS,
    RETRY_BASE_DELAY,
    ToolCall,
    create_message,
    get_tool_calls,
)

_PASS_THRESHOLD = 0.80


class Skill(TypedDict):
    name: str
    description: str


def _use_cases_to_tests() -> list[pytest.param]:
    """Return (skill_name, queries) test pairs from every use_cases.yaml in the tree."""
    skills_root = Path(__file__).parent.parent
    cases: list[pytest.param] = []
    for yaml_file in sorted(skills_root.rglob("use_cases.yaml")):
        skill_name = yaml_file.parent.name
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        queries = data.get("queries", [])
        if queries:
            cases.append(pytest.param(skill_name, queries, id=skill_name))
    return cases


@pytest.mark.parametrize(("skill", "queries"), _use_cases_to_tests())
async def test_skill_selection_accuracy(skill: str, queries: list[str]) -> None:
    skills = _load_skills()
    results: list[tuple[str, set[str], bool]] = []
    for query in queries:
        loaded = set(await _select_skills_for_query(query, skills))
        results.append((query, loaded, skill in loaded))

    passed = sum(1 for _, _, ok in results if ok)
    total = len(results)
    accuracy = passed / total if total > 0 else 0.0

    failed_queries = [(q, loaded) for q, loaded, ok in results if not ok]
    assert accuracy >= _PASS_THRESHOLD, (
        f"Skill '{skill}' accuracy {accuracy:.0%} is below the {_PASS_THRESHOLD:.0%} threshold "
        f"({passed}/{total} passed). Failed queries:\n"
        + "\n".join(
            f"  - {q} [Unexpected skill(s): {', '.join(sorted(loaded)) or 'No skills used!'}]"
            for q, loaded in failed_queries
        )
    )


async def _select_skills_for_query(
    user_message: str,
    skills: dict[str, Skill] | None = None,
) -> list[str]:
    """Return skill names that should be loaded for the given user message."""
    if skills is None:
        skills = _load_skills()

    if not skills:
        return []

    kwargs = {
        "model": HAIKU_MODEL,
        "max_tokens": 1000,
        "temperature": 0,
        "system": _build_system_prompt(skills),
        "tools": [_EVALUATE_SKILLS_TOOL],
        "tool_choice": {"type": "any"},
        "messages": [{"role": "user", "content": user_message}],
    }
    for attempt in range(MAX_ATTEMPTS):
        response = await create_message(**kwargs)
        tool_calls = get_tool_calls(response)
        if tool_calls:
            return _parse_evaluated_skills(tool_calls, skills)
        if attempt < MAX_ATTEMPTS - 1:
            await asyncio.sleep(RETRY_BASE_DELAY)

    # No skills were called across all attempts
    return []


def _load_skills() -> dict[str, Skill]:
    skills_root = Path(__file__).parent.parent
    result: dict[str, Skill] = {}
    for skill_file in sorted(skills_root.rglob("SKILL.md")):
        with skill_file.open(encoding="utf-8-sig") as f:
            post = frontmatter.load(f)
        if "name" not in post.metadata or "description" not in post.metadata:
            continue
        name = str(post.metadata["name"])
        description = str(post.metadata["description"])
        result[name] = Skill(name=name, description=description)
    return result


_SYSTEM_PROMPT_TEMPLATE = """\
You are a skill routing evaluator for an AI coding assistant. Analyze user messages to determine which skills should be loaded.

## What are Skills?
Skills extend the assistant's functionality with specialized instructions. Loading relevant skills improves task handling.

## Available Skills
{skill_defs}

## Your Task
For EACH skill, provide:
1. **confidence** (0.0 - 1.0): How confident the skill should be loaded
2. **reasoning**: Brief explanation

## Confidence Calibration
- **0.8 - 1.0**: EXPLICIT request for the skill's capability
- **0.6 - 0.8**: Strongly IMPLIED by context (skill clearly applies even if not stated)
- **0.3 - 0.6**: Related but ambiguous - user's intent unclear
- **0.0 - 0.3**: Not relevant

Threshold is 0.6 - skills scoring below this won't load.

## Guidelines
- Score 0.8+ for explicit requests, 0.6-0.8 for strongly implied
- Tangential mentions without clear intent → below 0.6
- General infrastructure tasks (create S3, EKS, Lambda) need NO skills

You MUST call the evaluate_skills tool.

## Examples (showing confidence spectrum)

### Example 1 - EXPLICIT terraform request → 0.9
User: "Convert my Terraform VPC configuration to Pulumi"
- pulumi-terraform-to-pulumi: 0.9 (explicit conversion request)
- ALL other skills: 0.0

### Example 2 - IMPLICIT terraform (strongly implied) → 0.7
User: "I have main.tf, variables.tf and outputs.tf from our old setup"
- pulumi-terraform-to-pulumi: 0.7 (old TF files imply conversion needed)
- ALL other skills: 0.0

### Example 3 - Terraform MENTIONED but new project → 0.3
User: "We use Terraform but want to try Pulumi for a new project"
- pulumi-terraform-to-pulumi: 0.3 (NEW project = no migration needed)
- ALL other skills: 0.0

### Example 4 - Resource creation → NO skills
User: "Create an S3 bucket with Pulumi"
- ALL skills: 0.0 (general infrastructure task)

### Example 5 - Ambiguous query → below threshold
User: "How do I manage secrets?"
- pulumi-esc: 0.4 (ambiguous - could be config secrets, env vars, or ESC)
- ALL other skills: 0.0

### Example 6 - EXPLICIT ESC request → 0.9
User: "Set up OIDC authentication for AWS"
- pulumi-esc: 0.9 (OIDC is explicit ESC capability)
- ALL other skills: 0.0
"""


def _build_system_prompt(skills: dict[str, Skill]) -> str:
    skill_defs = "\n".join(
        f"### {s['name']}\n{s['description']}\n" for s in skills.values()
    )
    return _SYSTEM_PROMPT_TEMPLATE.format(skill_defs=skill_defs)


_EVALUATE_SKILLS_TOOL: anthropic.types.ToolParam = {
    "name": "evaluate_skills",
    "description": "Evaluate which skills should be loaded",
    "input_schema": {
        "type": "object",
        "properties": {
            "evaluations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reasoning": {"type": "string"},
                    },
                    "required": ["skill_name", "confidence", "reasoning"],
                },
            }
        },
        "required": ["evaluations"],
    },
}

_SKILL_CONFIDENCE_THRESHOLD = 0.6


def _parse_evaluated_skills(
    tool_calls: list[ToolCall], skills: dict[str, Skill]
) -> list[str]:
    result: list[str] = []
    for call in tool_calls:
        if call.name == "evaluate_skills":
            for eval_data in call.input.get("evaluations", []):
                skill_name = eval_data.get("skill_name")
                confidence = eval_data.get("confidence", 0.0)
                if skill_name in skills and confidence >= _SKILL_CONFIDENCE_THRESHOLD:
                    result.append(skill_name)
    return result
