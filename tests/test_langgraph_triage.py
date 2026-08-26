"""Tests for :mod:`langgraph_triage`.

No test touches a real model: every chain is a ``RunnableLambda`` stub or a
``FakeListChatModel``, so the suite passes with no API key and no network.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples"
    ),
)

from langchain_core.language_models.fake_chat_models import (  # noqa: E402
    FakeListChatModel,
)
from langchain_core.runnables import RunnableLambda  # noqa: E402

from langgraph_triage import (  # noqa: E402
    APPROVAL_TOKEN,
    FALLBACK_CATEGORY,
    build_classifier,
    build_drafter,
    build_graph,
    build_reviewer,
    escalate,
    finalize,
    initial_state,
    is_approved,
    make_classify_node,
    make_draft_node,
    make_review_node,
    normalize_category,
    route_after_classification,
    route_after_review,
)


def echo(value):
    """A stub runnable that ignores its input and returns ``value``."""
    return RunnableLambda(lambda _: value)


def recorder(inputs: list, value: str):
    """A stub runnable that appends each input to ``inputs`` before replying."""

    def _call(payload):
        inputs.append(payload)
        return value

    return RunnableLambda(_call)


def scripted(replies: list[str]):
    """A stub runnable that returns ``replies`` in order, one per call."""
    remaining = list(replies)

    def _call(_):
        return remaining.pop(0)

    return RunnableLambda(_call)


class NormalizeCategoryTests(unittest.TestCase):
    def test_exact_label_passes_through(self):
        self.assertEqual(normalize_category("billing"), "billing")

    def test_matching_is_case_insensitive_and_ignores_surrounding_prose(self):
        self.assertEqual(normalize_category("Category: Technical."), "technical")

    def test_whitespace_is_stripped(self):
        self.assertEqual(normalize_category("  account \n"), "account")

    def test_unknown_label_falls_back(self):
        self.assertEqual(normalize_category("feature request"), FALLBACK_CATEGORY)

    def test_empty_output_falls_back(self):
        self.assertEqual(normalize_category(""), FALLBACK_CATEGORY)


class IsApprovedTests(unittest.TestCase):
    def test_bare_token_approves(self):
        self.assertTrue(is_approved(APPROVAL_TOKEN))

    def test_token_is_matched_case_insensitively_with_padding(self):
        self.assertTrue(is_approved("  approve\n"))

    def test_token_must_lead_the_verdict(self):
        self.assertFalse(is_approved("I would not APPROVE this yet."))

    def test_a_critique_does_not_approve(self):
        self.assertFalse(is_approved("Too vague about the refund timeframe."))


class ClassifyNodeTests(unittest.TestCase):
    def test_returns_only_the_keys_it_owns(self):
        node = make_classify_node(echo("billing"))
        self.assertEqual(
            node(initial_state("I was charged twice")),
            {"category": "billing", "trail": ["classify"]},
        )

    def test_passes_the_ticket_text_to_the_chain(self):
        seen: list = []
        node = make_classify_node(recorder(seen, "technical"))
        node(initial_state("the dashboard 500s on save"))
        self.assertEqual(seen, [{"ticket": "the dashboard 500s on save"}])

    def test_normalizes_a_chatty_answer(self):
        node = make_classify_node(echo("This looks like an OUTAGE to me."))
        self.assertEqual(node(initial_state("everything is down"))["category"], "outage")


class DraftNodeTests(unittest.TestCase):
    def test_records_the_draft_and_spends_a_revision(self):
        node = make_draft_node(echo("  We refunded the duplicate charge.  "))
        state = initial_state("double charged")
        result = node(state)
        self.assertEqual(result["draft"], "We refunded the duplicate charge.")
        self.assertEqual(result["revisions"], 1)
        self.assertEqual(result["trail"], ["draft"])

    def test_revision_counter_builds_on_the_current_state(self):
        node = make_draft_node(echo("second attempt"))
        state = initial_state("double charged")
        state["revisions"] = 1
        self.assertEqual(node(state)["revisions"], 2)

    def test_forwards_category_and_critique_to_the_chain(self):
        seen: list = []
        node = make_draft_node(recorder(seen, "fixed"))
        state = initial_state("double charged")
        state["category"] = "billing"
        state["critique"] = "No refund timeframe."
        node(state)
        self.assertEqual(
            seen,
            [
                {
                    "ticket": "double charged",
                    "category": "billing",
                    "critique": "No refund timeframe.",
                }
            ],
        )


class ReviewNodeTests(unittest.TestCase):
    def test_approval_clears_the_critique(self):
        node = make_review_node(echo(APPROVAL_TOKEN))
        state = initial_state("double charged")
        state["draft"] = "A good reply."
        state["critique"] = "stale objection"
        self.assertEqual(
            node(state),
            {"approved": True, "critique": "", "trail": ["review"]},
        )

    def test_rejection_stores_the_critique(self):
        node = make_review_node(echo("  No refund timeframe.  "))
        state = initial_state("double charged")
        state["draft"] = "Sorry about that."
        result = node(state)
        self.assertFalse(result["approved"])
        self.assertEqual(result["critique"], "No refund timeframe.")

    def test_passes_the_ticket_and_current_draft_to_the_chain(self):
        seen: list = []
        node = make_review_node(recorder(seen, APPROVAL_TOKEN))
        state = initial_state("double charged")
        state["draft"] = "Sorry about that."
        node(state)
        self.assertEqual(
            seen, [{"ticket": "double charged", "draft": "Sorry about that."}]
        )


class TerminalNodeTests(unittest.TestCase):
    def test_finalize_resolves(self):
        self.assertEqual(
            finalize(initial_state("t")),
            {"outcome": "resolved", "trail": ["finalize"]},
        )

    def test_escalate_hands_over(self):
        self.assertEqual(
            escalate(initial_state("t")),
            {"outcome": "escalated", "trail": ["escalate"]},
        )


class RouteAfterClassificationTests(unittest.TestCase):
    def _state(self, category: str):
        state = initial_state("t")
        state["category"] = category
        return state

    def test_outage_skips_drafting(self):
        self.assertEqual(route_after_classification(self._state("outage")), "escalate")

    def test_billing_gets_a_draft(self):
        self.assertEqual(route_after_classification(self._state("billing")), "draft")

    def test_fallback_category_still_gets_a_draft(self):
        self.assertEqual(
            route_after_classification(self._state(FALLBACK_CATEGORY)), "draft"
        )


class RouteAfterReviewTests(unittest.TestCase):
    def _state(self, *, approved: bool, revisions: int, max_revisions: int = 2):
        state = initial_state("t", max_revisions=max_revisions)
        state["approved"] = approved
        state["revisions"] = revisions
        return state

    def test_approved_draft_is_finalized(self):
        self.assertEqual(
            route_after_review(self._state(approved=True, revisions=1)), "finalize"
        )

    def test_rejected_draft_within_budget_loops_back(self):
        self.assertEqual(
            route_after_review(self._state(approved=False, revisions=1)), "draft"
        )

    def test_budget_exhausted_escalates(self):
        self.assertEqual(
            route_after_review(self._state(approved=False, revisions=2)), "escalate"
        )

    def test_approval_wins_over_an_exhausted_budget(self):
        self.assertEqual(
            route_after_review(self._state(approved=True, revisions=2)), "finalize"
        )

    def test_a_zero_budget_escalates_immediately(self):
        self.assertEqual(
            route_after_review(
                self._state(approved=False, revisions=0, max_revisions=0)
            ),
            "escalate",
        )


class GraphTests(unittest.TestCase):
    """End-to-end runs of the compiled graph, always with stub runnables."""

    def _graph(self, category: str, drafts: list[str], verdicts: list[str]):
        return build_graph(echo(category), scripted(drafts), scripted(verdicts))

    def test_first_draft_approved_runs_straight_through(self):
        graph = self._graph("billing", ["A good reply."], [APPROVAL_TOKEN])
        final = graph.invoke(initial_state("charged twice"))
        self.assertEqual(
            final["trail"], ["classify", "draft", "review", "finalize"]
        )
        self.assertEqual(final["outcome"], "resolved")
        self.assertEqual(final["draft"], "A good reply.")
        self.assertEqual(final["revisions"], 1)
        self.assertTrue(final["approved"])

    def test_rejected_draft_loops_back_and_carries_the_critique(self):
        graph = self._graph(
            "billing",
            ["Sorry about that.", "Refunded, 5-10 business days."],
            ["Give a refund timeframe.", APPROVAL_TOKEN],
        )
        final = graph.invoke(initial_state("charged twice"))
        self.assertEqual(
            final["trail"],
            ["classify", "draft", "review", "draft", "review", "finalize"],
        )
        self.assertEqual(final["outcome"], "resolved")
        self.assertEqual(final["draft"], "Refunded, 5-10 business days.")
        self.assertEqual(final["revisions"], 2)
        # The approving review clears the objection it started with.
        self.assertEqual(final["critique"], "")

    def test_the_critique_reaches_the_next_draft(self):
        seen: list = []
        graph = build_graph(
            echo("billing"),
            recorder(seen, "another attempt"),
            scripted(["Give a refund timeframe.", APPROVAL_TOKEN]),
        )
        graph.invoke(initial_state("charged twice"))
        self.assertEqual(seen[0]["critique"], "")
        self.assertEqual(seen[1]["critique"], "Give a refund timeframe.")

    def test_loop_terminates_and_escalates_when_the_budget_runs_out(self):
        graph = self._graph(
            "technical",
            ["draft one", "draft two"],
            ["still wrong", "still wrong"],
        )
        final = graph.invoke(initial_state("cannot export data", max_revisions=2))
        self.assertEqual(
            final["trail"],
            ["classify", "draft", "review", "draft", "review", "escalate"],
        )
        self.assertEqual(final["outcome"], "escalated")
        self.assertEqual(final["revisions"], 2)
        self.assertFalse(final["approved"])
        self.assertEqual(final["critique"], "still wrong")

    def test_a_larger_budget_allows_more_passes_before_escalating(self):
        graph = self._graph(
            "technical",
            ["one", "two", "three"],
            ["no", "no", "no"],
        )
        final = graph.invoke(initial_state("cannot export data", max_revisions=3))
        self.assertEqual(final["revisions"], 3)
        self.assertEqual(final["trail"].count("draft"), 3)
        self.assertEqual(final["outcome"], "escalated")

    def test_outage_escalates_without_drafting(self):
        graph = self._graph("outage", [], [])
        final = graph.invoke(initial_state("everything returns 503"))
        self.assertEqual(final["trail"], ["classify", "escalate"])
        self.assertEqual(final["outcome"], "escalated")
        self.assertEqual(final["draft"], "")
        self.assertEqual(final["revisions"], 0)

    def test_graph_runs_against_fake_chat_models(self):
        """The same wiring, driven through real prompt | model | parser chains."""
        graph = build_graph(
            build_classifier(FakeListChatModel(responses=["billing"])),
            build_drafter(FakeListChatModel(responses=["Refunded today."])),
            build_reviewer(FakeListChatModel(responses=[APPROVAL_TOKEN])),
        )
        final = graph.invoke(initial_state("charged twice"))
        self.assertEqual(final["category"], "billing")
        self.assertEqual(final["draft"], "Refunded today.")
        self.assertEqual(final["outcome"], "resolved")


class PromptTests(unittest.TestCase):
    """The prompts are part of the contract, so assert on what they carry."""

    def test_classifier_prompt_lists_every_allowed_category(self):
        prompt = build_classifier(FakeListChatModel(responses=["billing"])).steps[0]
        rendered = prompt.invoke({"ticket": "charged twice"}).to_string()
        self.assertIn("charged twice", rendered)
        for category in ("billing", "technical", "account", "outage"):
            self.assertIn(category, rendered)

    def test_reviewer_prompt_names_the_approval_token(self):
        prompt = build_reviewer(FakeListChatModel(responses=["x"])).steps[0]
        rendered = prompt.invoke({"ticket": "t", "draft": "d"}).to_string()
        self.assertIn(APPROVAL_TOKEN, rendered)

    def test_drafter_prompt_carries_the_critique(self):
        prompt = build_drafter(FakeListChatModel(responses=["x"])).steps[0]
        rendered = prompt.invoke(
            {"ticket": "t", "category": "billing", "critique": "too vague"}
        ).to_string()
        self.assertIn("too vague", rendered)
        self.assertIn("billing", rendered)


if __name__ == "__main__":
    unittest.main()
