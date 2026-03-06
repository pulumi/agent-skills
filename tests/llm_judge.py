"""LLM Judge for evaluating agent responses.

Inlined from pulumi-service, with agents_py dependencies removed.
Supports both Anthropic API (via ANTHROPIC_API_KEY) and Bedrock (via AWS creds).
"""

import os

import anthropic
from anthropic.types.tool_choice_tool_param import ToolChoiceToolParam
from anthropic.types.tool_union_param import ToolParam
from pydantic import BaseModel

DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _create_client_and_model() -> tuple[anthropic.Anthropic | anthropic.AnthropicBedrock, str]:
    """Create an Anthropic client, using direct API or Bedrock depending on env."""
    if os.getenv("ANTHROPIC_API_KEY") is not None:
        return anthropic.Anthropic(), DEFAULT_MODEL
    client = anthropic.AnthropicBedrock()
    bedrock_model = f"us.anthropic.{DEFAULT_MODEL}-v1:0"
    return client, bedrock_model


class LLMJudgeBooleanResult(BaseModel):
    reasoning: str
    answer: bool


def llm_judge_boolean(content: str, evaluation_prompt: str) -> LLMJudgeBooleanResult:
    """Generic LLM judge that evaluates content against a prompt and returns a boolean result."""

    client, model = _create_client_and_model()
    response = client.messages.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": f"{evaluation_prompt}\n\nContent to evaluate:\n{content}",
            }
        ],
        max_tokens=10000,
        system=[
            anthropic.types.TextBlockParam(
                type="text",
                text="You are an expert evaluator. Analyze the content carefully against the given criteria and provide your reasoning and a yes/no answer. Use the record_judgment tool to record your evaluation.",
            )
        ],
        temperature=0.0,
        tools=[
            ToolParam(
                name="record_judgment",
                description="Record the reasoning and yes/no answer for an evaluation",
                input_schema={
                    "type": "object",
                    "properties": {
                        "reasoning": {
                            "type": "string",
                            "description": "Detailed reasoning for your evaluation",
                        },
                        "answer": {
                            "type": "string",
                            "description": "Your final answer: 'yes' or 'no'",
                            "enum": ["yes", "no"],
                        },
                    },
                    "required": ["reasoning", "answer"],
                },
            ),
        ],
        tool_choice=ToolChoiceToolParam(
            type="tool",
            name="record_judgment",
        ),
    )

    result = response.content[-1]
    assert isinstance(result, anthropic.types.ToolUseBlock), (
        f"Expected a tool use block, got {result.model_dump_json(by_alias=True)}"
    )
    assert isinstance(result.input, dict), (
        f"Expected dict for tool_args, got {type(result.input)}"
    )
    tool_args = result.input
    print(
        f"""
LLM Judge Evaluation:
Reasoning: {tool_args["reasoning"]}
Answer: {tool_args["answer"]}
"""
    )

    answer = tool_args["answer"]
    if answer not in ["yes", "no"]:
        raise ValueError(f"Unexpected answer: {answer}")
    reasoning = tool_args["reasoning"]
    assert isinstance(reasoning, str), (
        f"Expected str for reasoning, got {type(reasoning).__name__}"
    )
    return LLMJudgeBooleanResult(reasoning=reasoning, answer=answer == "yes")
