"""
LLM judge tests for skill quality.

For each SKILL.md in the tree, an LLM evaluates the skill against a quality
rubric derived from skill authoring best practices. The test fails when any
HIGH-severity issue is found, so quality problems surface in CI.

Requires ANTHROPIC_API_KEY to be set in the environment.

Run with:
    uv run pytest tests/test_skill_quality.py -v -s
"""

from pathlib import Path

import pytest
from llm_client import SONNET_MODEL, create_message, get_tool_calls

_REPORT_TOOL = {
    "name": "report_review",
    "description": "Submit the quality review of the skill.",
    "input_schema": {
        "type": "object",
        "properties": {
            "overall_score": {"type": "integer", "minimum": 0, "maximum": 10},
            "summary": {"type": "string"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                        "area": {
                            "type": "string",
                            "enum": ["description", "body", "structure", "progressive_disclosure"],
                        },
                        "description": {"type": "string"},
                        "suggestion": {"type": "string"},
                    },
                    "required": ["severity", "area", "description", "suggestion"],
                },
            },
        },
        "required": ["overall_score", "summary", "issues"],
    },
}


def _skills_to_tests() -> list[pytest.param]:
    """Return (skill_name, skill_content) pytest params for every SKILL.md."""
    skills_root = Path(__file__).parent.parent
    cases: list[pytest.param] = []
    for skill_file in sorted(skills_root.rglob("SKILL.md")):
        skill_name = skill_file.parent.name
        content = skill_file.read_text(encoding="utf-8")
        cases.append(pytest.param(skill_name, content, id=skill_name))
    return cases


@pytest.mark.parametrize(("skill_name", "skill_content"), _skills_to_tests())
async def test_skill_quality(skill_name: str, skill_content: str) -> None:
    kwargs = {
        "model": SONNET_MODEL,
        "max_tokens": 4096,
        "temperature": 0,
        "tools": [_REPORT_TOOL],
        "tool_choice": {"type": "tool", "name": _REPORT_TOOL["name"]},
        "system": _QUALITY_JUDGEMENT_SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Please review this skill:\n\n```\n{skill_content}\n```",
            }
        ],
    }
    # Forcing a tool call makes the API return the review as parsed JSON.
    # Asking for raw JSON text failed whenever the judge quoted the skill with
    # unescaped double quotes, and at temperature 0 retries repeat the same text.
    response = await create_message(**kwargs)
    calls = [c for c in get_tool_calls(response) if c.name == _REPORT_TOOL["name"]]
    if not calls:
        pytest.fail(f"Judge did not call {_REPORT_TOOL['name']}: {response.content}")
    result: dict = calls[0].input

    score: int = result.get("overall_score", 0)
    summary: str = result.get("summary", "")
    issues: list[dict] = result.get("issues", [])

    high_issues = [i for i in issues if i.get("severity") == "high"]
    medium_issues = [i for i in issues if i.get("severity") == "medium"]
    low_issues = [i for i in issues if i.get("severity") == "low"]

    # Always print the full critique for visibility
    lines = [f"\nSkill: {skill_name}"]
    for issue in issues:
        sev = issue.get("severity", "?").upper()
        area = issue.get("area", "?")
        desc = issue.get("description", "")
        suggestion = issue.get("suggestion", "")
        lines.append(f"\n  [{sev}] {area}")
        lines.append(f"    Problem:    {desc}")
        lines.append(f"    Suggestion: {suggestion}")

    print("\n".join(lines))

    if high_issues:
        issues_text = "\n".join(
            f"  [{i['area']}] {i['description']} → {i['suggestion']}"
            for i in high_issues
        )
        pytest.fail(
            f"Skill '{skill_name}' has {len(high_issues)} HIGH-severity issue(s):\n{issues_text}\n\n"
            f"Also found: {len(medium_issues)} medium, {len(low_issues)} low. "
            f"Overall score: {score}/10. {summary}"
        )


_QUALITY_JUDGEMENT_SYSTEM_PROMPT = """\
You are a quality reviewer for AI agent skills. A "skill" is a SKILL.md file
that an AI agent loads to handle specialised tasks. Your job is to identify
concrete, actionable improvements.

## What makes a good skill

### Description (frontmatter `description` field)
The description is the ONLY thing a routing model sees when deciding whether to
load a skill. It must:
- State clearly WHAT the skill does
- State clearly WHEN to load it — specific trigger phrases, user intents, and
  contexts that activate this skill
- Be slightly "pushy" — err on the side of activating when relevant, because
  models tend to undertrigger
- Be self-contained: a router should not need to read the body to make a
  correct load/no-load decision
- Avoid false-positive triggers: near-miss scenarios (similar topic, different
  need) should not accidentally match

### Body instructions
- **Explain WHY**, not just what: instructions should convey the reasoning
  behind each step so the model can generalise. If you see `MUST`/`ALWAYS`/
  `NEVER` in all-caps without a rationale, that is a yellow flag.
- **Lean**: nothing should be present that isn't pulling its weight. Redundant,
  vague, or boilerplate content dilutes the instructions.
- **Imperative form**: instructions should be written as commands ("Do X",
  "Return Y"), not as descriptions ("The model should do X").
- **Output format**: the skill should define what a correct response looks like,
  either with a template, example, or explicit description.
- **Edge cases**: foreseeable failure modes or ambiguous situations should be
  addressed, either inline or with a pointer to a reference file.

### Progressive disclosure
- SKILL.md body should stay under ~500 lines. Detailed reference material
  belongs in separate files (e.g. `references/`, `agents/`) linked from the
  body with clear guidance on when to read them.
- Large reference files (>300 lines) should have a table of contents.

## Severity levels
- **high**: The skill will likely misbehave or fail to trigger/avoid-trigger
  correctly. Needs fixing before the skill is useful.
- **medium**: The skill works but is noticeably weaker than it could be.
  Worth fixing soon.
- **low**: Minor polish. Nice to have.

## Output format
Submit your review by calling the `report_review` tool. Give an integer
`overall_score` from 0 to 10 (10 is excellent), a two-sentence `summary`, and
one `issues` entry per problem with its severity, area, a specific description
(quoting the skill where helpful) and a concrete suggestion.

If the skill is excellent, return an empty `issues` array.
"""
