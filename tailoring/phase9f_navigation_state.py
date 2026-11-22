"""Session-only editable preferences, independent of Streamlit widget cleanup.

These values are never analysis, confirmation, generation or approval authority.
Consumers must still validate current input/ranking/source fingerprints.
"""
from __future__ import annotations

from typing import Any, Callable

STATE_KEY = "phase9f_navigation_preferences"
MAX_PREFERENCES = 64


def _remember(state: Any, key: str, scope: str, identity: Callable | None) -> None:
    value = state.get(key)
    token = identity(value) if identity is not None and value is not None else value
    preferences = dict(state.get(STATE_KEY) or {})
    preferences.pop(key, None)
    preferences[key] = {"scope": scope, "value": token}
    while len(preferences) > MAX_PREFERENCES:
        preferences.pop(next(iter(preferences)))
    state[STATE_KEY] = preferences


def navigation_selectbox(st: Any, label: str, options: Any, *, key: str,
                         scope: str = "", identity: Callable | None = None,
                         **kwargs: Any) -> Any:
    """Restore an available identity using fresh option records, never old rows."""
    options = list(options)
    state = st.session_state
    remembered = (state.get(STATE_KEY) or {}).get(key, {})
    token_of = identity or (lambda value: value)
    has_preference = key in state or (
        remembered.get("scope") == scope and "value" in remembered
    )
    if key in state:
        current = state[key]
        token = token_of(current) if current is not None else None
    elif remembered.get("scope") == scope:
        token = remembered.get("value")
    else:
        token = None
    matches = [value for value in options if token_of(value) == token] if has_preference else []
    # Scope changes invalidate a live widget as well as its durable preference.
    scope_changed = bool(remembered and remembered.get("scope") != scope)
    if matches and not scope_changed:
        state[key] = matches[0]
    elif key in state:
        del state[key]
    selected = st.selectbox(
        label, options, key=key, on_change=_remember,
        args=(state, key, scope, identity), **kwargs,
    )
    _remember(state, key, scope, identity)
    return selected


def navigation_text(st: Any, label: str, *, key: str, scope: str = "",
                    multiline: bool = False, **kwargs: Any) -> str:
    state = st.session_state
    remembered = (state.get(STATE_KEY) or {}).get(key, {})
    if key not in state and remembered.get("scope") == scope:
        if isinstance(remembered.get("value"), str):
            state[key] = remembered["value"]
    if key in state:
        kwargs.pop("value", None)
    widget = st.text_area if multiline else st.text_input
    value = widget(label, key=key, on_change=_remember,
                   args=(state, key, scope, None), **kwargs)
    _remember(state, key, scope, None)
    return value


def navigation_checkbox(st: Any, label: str, *, key: str, **kwargs: Any) -> bool:
    """Only for harmless view preferences, never confirmations/acknowledgments."""
    state = st.session_state
    remembered = (state.get(STATE_KEY) or {}).get(key, {})
    if key not in state and isinstance(remembered.get("value"), bool):
        state[key] = remembered["value"]
    if key in state:
        kwargs.pop("value", None)
    value = st.checkbox(label, key=key, on_change=_remember,
                        args=(state, key, "", None), **kwargs)
    _remember(state, key, "", None)
    return value
