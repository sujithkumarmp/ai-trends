# Examples

## `langchain_basic.py`

A minimal LangChain chain built with LCEL: a `ChatPromptTemplate` piped into a
chat model and a `StrOutputParser`. It demonstrates the three ways to run any
LCEL runnable — `invoke`, `batch` and `stream`.

### Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r examples/requirements.txt
```

### Run

```bash
.venv/bin/python examples/langchain_basic.py
```

With `ANTHROPIC_API_KEY` exported, the chain calls Claude (`claude-opus-5`)
through `langchain-anthropic`. Without a key it falls back to
`FakeListChatModel`, so the example is still runnable offline and in CI — the
chain wiring is identical either way, only the model swaps.

## `langgraph_triage.py`

A LangGraph state machine that triages a support ticket: classify it, draft a
reply, review the draft, and loop back to the drafter with the critique until
the reviewer approves or the revision budget runs out — at which point the
ticket is escalated to a human. Outage tickets skip drafting entirely.

```
                    ┌──────────── outage ────────────┐
START ─► classify ──┤                                ▼
                    └─ otherwise ─► draft ─► review ─► escalate (budget spent)
                                      ▲        │
                                      └ revise ┘  └─► finalize (approved)
```

It shows what a graph adds over an LCEL chain: a `TypedDict` state shared by
every node (with an `operator.add` reducer accumulating the visited-node
trail), two conditional edges that pick the next node from that state, and a
`review -> draft` cycle bounded by a revision counter.

### Run

```bash
.venv/bin/python examples/langgraph_triage.py
```

Same model story as above: real Claude with a key, `FakeListChatModel`
without one. Unit tests live in `tests/test_langgraph_triage.py` and drive
every node, both routers, and the compiled graph with stub runnables only.
