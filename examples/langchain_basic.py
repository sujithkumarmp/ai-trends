"""A basic LangChain example: prompt -> chat model -> string output parser.

The chain is built with LangChain Expression Language (LCEL), so the same
object supports ``invoke``, ``batch`` and ``stream``.

Run it with a real model by exporting an API key first::

    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/langchain_basic.py

Without a key the script falls back to a deterministic fake chat model, so the
example still runs end to end (useful in CI or offline).
"""

from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

MODEL = "claude-opus-5"

SYSTEM_PROMPT = (
    "You are a concise technical explainer. Answer in a single short paragraph "
    "that a working software engineer can act on."
)

# Canned answers used when no API key is configured. FakeListChatModel cycles
# through this list, one response per model call.
OFFLINE_RESPONSES = [
    "LCEL is LangChain's composition syntax: piping a prompt, a model and a "
    "parser with `|` produces a Runnable that supports invoke, batch and "
    "stream without any extra glue code.",
    "A retriever turns a query into relevant documents; a chain then stuffs "
    "those documents into the prompt so the model answers from your data "
    "rather than from memory alone.",
    "Structured output binds a schema to the model call, so you get a "
    "validated object back instead of prose you have to parse yourself.",
]


def build_model() -> BaseChatModel:
    """Return a Claude chat model, or a fake one when no API key is set."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
        )

    print("ANTHROPIC_API_KEY is not set - using a fake chat model.\n")
    return FakeListChatModel(responses=OFFLINE_RESPONSES)


def build_chain(model: BaseChatModel) -> Runnable:
    """Compose prompt -> model -> parser into a single runnable."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "Explain {topic} to a developer new to LangChain."),
        ]
    )
    return prompt | model | StrOutputParser()


def main() -> None:
    chain = build_chain(build_model())

    print("== invoke ==")
    print(chain.invoke({"topic": "LangChain Expression Language"}), "\n")

    print("== batch ==")
    for topic, answer in zip(
        ["retrievers", "structured output"],
        chain.batch([{"topic": "retrievers"}, {"topic": "structured output"}]),
    ):
        print(f"- {topic}: {answer}")
    print()

    print("== stream ==")
    for chunk in chain.stream({"topic": "LangChain Expression Language"}):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    main()
