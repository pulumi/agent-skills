"""
LLM judge tests for skill quality.

For each SKILL.md in the tree, an LLM evaluates the skill against a quality
rubric derived from skill authoring best practices. The test fails when any
HIGH-severity issue is found, so quality problems surface in CI.

Requires ANTHROPIC_API_KEY to be set in the environment.

Run with:
    uv run pytest tests/test_skill_quality.py -v -s
"""

import asyncio
import json
from pathlib import Path

import pytest
from llm_client import MAX_ATTEMPTS, RETRY_BASE_DELAY, SONNET_MODEL, create_message


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
        "system": _QUALITY_JUDGEMENT_SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Please review this skill:\n\n```\n{skill_content}\n```",
            }
        ],
    }
    result: dict = {}
    for attempt in range(MAX_ATTEMPTS):
        response = await create_message(**kwargs)
        raw = response.content[0].text  # type: ignore[union-attr]
        try:
            result = json.loads(raw)
            break
        except json.JSONDecodeError:
            if attempt >= MAX_ATTEMPTS - 1:
                pytest.fail(
                    f"Judge returned non-JSON response after all retries:\n{raw}"
                )
            await asyncio.sleep(RETRY_BASE_DELAY)

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
Respond with ONLY a JSON object — no markdown fences, no explanation outside
the JSON:

{
  "overall_score": <integer 0-10, where 10 is excellent>,
  "summary": "<two-sentence overall assessment>",
  "issues": [
    {
      "severity": "high" | "medium" | "low",
      "area": "description" | "body" | "structure" | "progressive_disclosure",
      "description": "<specific problem, quoting the skill where helpful>",
      "suggestion": "<concrete fix>"
    }
  ]
}

If the skill is excellent, return an empty `issues` array.
"""
