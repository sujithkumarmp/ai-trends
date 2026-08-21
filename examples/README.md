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
