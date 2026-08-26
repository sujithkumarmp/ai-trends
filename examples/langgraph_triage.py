"""A LangGraph example: support-ticket triage with a bounded revision loop.

Where an LCEL chain is a straight pipe, this is a small state machine. A
support ticket is classified, a reply is drafted, and a reviewer node grades
that draft. An unapproved draft loops back to the drafter with the critique
attached, up to ``max_revisions`` times; anything still unapproved after that
is escalated to a human instead of being sent. Outage tickets skip drafting
altogether and escalate straight away.

That gives the three things a chain cannot express on its own:

* **state** - a ``TypedDict`` every node reads from and writes a slice of,
  including a ``trail`` list that accumulates through an ``operator.add``
  reducer;
* **conditional edges** - ``route_after_classification`` and
  ``route_after_review`` pick the next node from the current state;
* **a cycle** - ``review -> draft -> review``, bounded by a revision counter
  so it always terminates.

Run it with a real model by exporting an API key first::

    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/langgraph_triage.py

Without a key the script falls back to deterministic fake chat models, so the
example still runs end to end (useful in CI or offline).
"""

from __future__ import annotations

import operator
import os
from typing import Annotated, Callable, Literal, Sequence, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph

MODEL = "claude-opus-5"

#: Categories the classifier is allowed to return. Anything else becomes
#: ``FALLBACK_CATEGORY``, so a chatty model cannot invent a routing target.
CATEGORIES = ("billing", "technical", "account", "outage")
FALLBACK_CATEGORY = "general"

#: Tickets in this category never get an automated reply - a widespread
#: outage needs a human owner, not a polished apology.
ESCALATE_ON_SIGHT = "outage"

#: The reviewer signals "good enough to send" with this exact word.
APPROVAL_TOKEN = "APPROVE"


class TriageState(TypedDict):
    """State threaded through the triage graph.

    Attributes:
        ticket: The raw customer message.
        category: One of :data:`CATEGORIES`, or :data:`FALLBACK_CATEGORY`.
        draft: The most recent proposed reply.
        critique: The reviewer's objection to ``draft``; empty once approved.
        approved: Whether the reviewer signed off on ``draft``.
        revisions: How many drafts have been written so far.
        max_revisions: Drafting budget; the loop stops once it is spent.
        outcome: ``"resolved"``, ``"escalated"`` or empty while in flight.
        trail: Node names in visit order, accumulated across the run.
    """

    ticket: str
    category: str
    draft: str
    critique: str
    approved: bool
    revisions: int
    max_revisions: int
    outcome: str
    trail: Annotated[list[str], operator.add]


def initial_state(ticket: str, *, max_revisions: int = 2) -> TriageState:
    """Return a fully populated starting state for ``ticket``.

    Every key is set explicitly so nodes and routers can read the state
    without defensive ``.get`` calls.
    """
    return TriageState(
        ticket=ticket,
        category="",
        draft="",
        critique="",
        approved=False,
        revisions=0,
        max_revisions=max_revisions,
        outcome="",
        trail=[],
    )


def normalize_category(raw: str) -> str:
    """Map free-form model output onto one of :data:`CATEGORIES`.

    Matching is case-insensitive and substring-based, so "Category: Billing."
    still resolves to ``"billing"``. Unrecognised text yields
    :data:`FALLBACK_CATEGORY`.
    """
    text = raw.strip().lower()
    for category in CATEGORIES:
        if category in text:
            return category
    return FALLBACK_CATEGORY


def is_approved(raw: str) -> bool:
    """Return whether the reviewer's verdict ``raw`` approves the draft."""
    return raw.strip().upper().startswith(APPROVAL_TOKEN)


def build_model(offline_responses: Sequence[str]) -> BaseChatModel:
    """Return a Claude chat model, or a fake one replaying ``offline_responses``.

    ``FakeListChatModel`` cycles through the list, one response per call, which
    keeps the offline demo deterministic even across the revision loop.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
        )

    return FakeListChatModel(responses=list(offline_responses))


def build_classifier(model: BaseChatModel) -> Runnable:
    """Chain that labels a ticket with one of :data:`CATEGORIES`."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You triage customer support tickets. Reply with exactly one "
                "word from this list and nothing else: "
                + ", ".join(CATEGORIES)
                + ".",
            ),
            ("human", "{ticket}"),
        ]
    )
    return prompt | model | StrOutputParser()


def build_drafter(model: BaseChatModel) -> Runnable:
    """Chain that writes a reply, optionally addressing a prior critique."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a support agent. Write a reply of at most three "
                "sentences: acknowledge the problem, state the next concrete "
                "step, and give a timeframe. No promises you cannot keep.",
            ),
            (
                "human",
                "Category: {category}\nTicket: {ticket}\n\n"
                "Reviewer feedback on your previous draft (empty if this is "
                "your first attempt):\n{critique}",
            ),
        ]
    )
    return prompt | model | StrOutputParser()


def build_reviewer(model: BaseChatModel) -> Runnable:
    """Chain that grades a draft: ``APPROVE`` or a one-line objection."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You review support replies before they are sent. If the "
                f"draft is accurate, specific and polite, reply with exactly "
                f"{APPROVAL_TOKEN}. Otherwise reply with one sentence naming "
                "the single biggest problem.",
            ),
            ("human", "Ticket: {ticket}\n\nDraft reply: {draft}"),
        ]
    )
    return prompt | model | StrOutputParser()


# --- Nodes -----------------------------------------------------------------
#
# Each factory closes over the runnable it needs and returns a node function
# of the shape LangGraph expects: state in, partial state out. Tests drive the
# nodes directly by passing a stub runnable.


def make_classify_node(classifier: Runnable) -> Callable[[TriageState], dict]:
    """Node that fills in ``category`` from the ticket text."""

    def classify(state: TriageState) -> dict:
        raw = classifier.invoke({"ticket": state["ticket"]})
        return {"category": normalize_category(raw), "trail": ["classify"]}

    return classify


def make_draft_node(drafter: Runnable) -> Callable[[TriageState], dict]:
    """Node that writes the next draft and spends one revision."""

    def draft(state: TriageState) -> dict:
        reply = drafter.invoke(
            {
                "ticket": state["ticket"],
                "category": state["category"],
                "critique": state["critique"],
            }
        )
        return {
            "draft": reply.strip(),
            "revisions": state["revisions"] + 1,
            "trail": ["draft"],
        }

    return draft


def make_review_node(reviewer: Runnable) -> Callable[[TriageState], dict]:
    """Node that grades the current draft and records any critique."""

    def review(state: TriageState) -> dict:
        verdict = reviewer.invoke(
            {"ticket": state["ticket"], "draft": state["draft"]}
        )
        approved = is_approved(verdict)
        return {
            "approved": approved,
            "critique": "" if approved else verdict.strip(),
            "trail": ["review"],
        }

    return review


def finalize(state: TriageState) -> dict:
    """Terminal node for an approved draft."""
    return {"outcome": "resolved", "trail": ["finalize"]}


def escalate(state: TriageState) -> dict:
    """Terminal node for anything a human has to take over."""
    return {"outcome": "escalated", "trail": ["escalate"]}


# --- Routers ---------------------------------------------------------------


def route_after_classification(state: TriageState) -> Literal["draft", "escalate"]:
    """Send outages straight to a human; everything else gets a draft."""
    if state["category"] == ESCALATE_ON_SIGHT:
        return "escalate"
    return "draft"


def route_after_review(state: TriageState) -> Literal["draft", "finalize", "escalate"]:
    """Close the loop: approve, revise once more, or hand over.

    The revision budget is what makes the ``review -> draft`` cycle safe: once
    ``revisions`` reaches ``max_revisions`` the only way out is ``escalate``.
    """
    if state["approved"]:
        return "finalize"
    if state["revisions"] >= state["max_revisions"]:
        return "escalate"
    return "draft"


def build_graph(
    classifier: Runnable, drafter: Runnable, reviewer: Runnable
) -> Runnable:
    """Wire the nodes and edges together and compile the graph."""
    builder = StateGraph(TriageState)
    builder.add_node("classify", make_classify_node(classifier))
    builder.add_node("draft", make_draft_node(drafter))
    builder.add_node("review", make_review_node(reviewer))
    builder.add_node("finalize", finalize)
    builder.add_node("escalate", escalate)

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route_after_classification,
        {"draft": "draft", "escalate": "escalate"},
    )
    builder.add_edge("draft", "review")
    builder.add_conditional_edges(
        "review",
        route_after_review,
        # The "draft" arm is the cycle - it points back at a node the run has
        # already visited, which a plain DAG cannot do.
        {"draft": "draft", "finalize": "finalize", "escalate": "escalate"},
    )
    builder.add_edge("finalize", END)
    builder.add_edge("escalate", END)
    return builder.compile()


# --- Demo ------------------------------------------------------------------

REVISION_TICKET = (
    "I was charged twice for my August subscription - order #A-4471 shows two "
    "identical $49 payments on the same day. Please refund one of them."
)

OUTAGE_TICKET = (
    "None of our team can log in, the dashboard has been returning 503 for the "
    "last twenty minutes. Is something down?"
)

# One canned response per model call, in the order the graph makes them.
REVISION_CLASSIFIER_RESPONSES = ["billing"]
REVISION_DRAFTER_RESPONSES = [
    "Sorry about that! We'll look into the duplicate charge.",
    "Thanks for flagging order #A-4471 - I can see the duplicate $49 charge. "
    "I've submitted a refund for the second payment. It should reach your "
    "card within 5-10 business days.",
]
REVISION_REVIEWER_RESPONSES = [
    "Too vague: it never confirms the duplicate charge or gives a refund "
    "timeframe.",
    APPROVAL_TOKEN,
]

OUTAGE_CLASSIFIER_RESPONSES = ["outage"]


def run_demo(title: str, state: TriageState, graph: Runnable) -> None:
    """Invoke ``graph`` on ``state`` and print the path it took."""
    final = graph.invoke(state)
    print(f"== {title} ==")
    print("path:      ", " -> ".join(final["trail"]))
    print("category:  ", final["category"])
    print("revisions: ", final["revisions"], f"(budget {final['max_revisions']})")
    print("outcome:   ", final["outcome"])
    print("reply:     ", final["draft"] or "(none - handed to a human)")
    print()


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set - using fake chat models.\n")

    revision_graph = build_graph(
        build_classifier(build_model(REVISION_CLASSIFIER_RESPONSES)),
        build_drafter(build_model(REVISION_DRAFTER_RESPONSES)),
        build_reviewer(build_model(REVISION_REVIEWER_RESPONSES)),
    )
    run_demo(
        "billing ticket, rejected once then approved",
        initial_state(REVISION_TICKET),
        revision_graph,
    )

    outage_graph = build_graph(
        build_classifier(build_model(OUTAGE_CLASSIFIER_RESPONSES)),
        build_drafter(build_model(REVISION_DRAFTER_RESPONSES)),
        build_reviewer(build_model(REVISION_REVIEWER_RESPONSES)),
    )
    run_demo(
        "outage ticket, escalated without drafting",
        initial_state(OUTAGE_TICKET),
        outage_graph,
    )


if __name__ == "__main__":
    main()
