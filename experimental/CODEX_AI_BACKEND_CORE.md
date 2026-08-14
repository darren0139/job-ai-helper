# Codex AI Backend Core POC

The stable application interface remains:

    feature code
        |
        v
    llm.ask_json(...) / llm.ask_text(...)
        |
        v
    backend router
       / \
      /   \
    API   Codex

Feature modules should not import `openai_codex` directly.

API remains the default for both analysis and chat. The already-proven JD Codex
adapter is the first operation refactored to travel through
`llm.ask_json(..., backend="codex")`.

Important:
- no automatic API -> Codex fallback;
- no automatic Codex -> API fallback;
- API model configuration stays on the existing LiteLLM path;
- Codex may use CODEX_MODEL, CODEX_ANALYSIS_MODEL, or CODEX_CHAT_MODEL;
- Codex uses an empty temporary cwd, Sandbox.read_only, and ephemeral threads;
- Codex calls do not enter the API-cost call ledger;
- Codex JSON is one-turn/fail-closed to avoid spending an extra correction turn;
- deterministic scoring, persistence, fitting, and canonical logic are unchanged.

A global Streamlit API/Codex switch is intentionally deferred until more
operations have been evaluated.
