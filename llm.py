"""
llm.py

Drop-in LiteLLM router for Job AI Helper.

Key behaviour:
- Separate runtime routes for analysis and chat.
- Supports GPT-5.6 Sol, Terra, and Luna in the Streamlit model selector.
- Uses max_completion_tokens with extra headroom for OpenAI reasoning models.
- Uses max_tokens for non-reasoning models such as GPT-4o mini.
- Sends reasoning_effort only to OpenAI GPT-5/o-series models.
- Omits temperature and seed for reasoning models.
- Limits malformed-JSON correction to two attempts by default.
- Does not silently retry empty responses.
- Provides optional per-request timing logs.
- Keeps the existing ask_json() and ask_text() signatures.

Recommended .env baseline:

    MODEL=openai/gpt-4o-mini
    ANALYSIS_MODEL=openai/gpt-4o-mini
    CHAT_MODEL=openai/gpt-4o-mini

    ANALYSIS_REASONING_EFFORT=low
    CHAT_REASONING_EFFORT=low

    LLM_JSON_ATTEMPTS=2
    LLM_API_RETRIES=3
    LLM_REQUEST_TIMEOUT_SECONDS=120
    LLM_REASONING_TOKEN_HEADROOM=2000
    LLM_MIN_REASONING_COMPLETION_TOKENS=4000
    LLM_DEBUG_TIMING=false

The reasoning settings are ignored automatically while a non-reasoning model
such as GPT-4o mini is selected.
"""

from __future__ import annotations

import json
import os
import sys
import time
from copy import deepcopy
from typing import Any, Literal

import litellm
from dotenv import load_dotenv
from litellm import completion


load_dotenv()

RouteName = Literal["analysis", "chat"]

# Let LiteLLM omit provider-specific parameters that are unsupported.
litellm.drop_params = True


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _env_flag(
    name: str,
    *,
    default: bool = False,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _env_positive_int(
    name: str,
    *,
    default: int,
) -> int:
    value = os.getenv(name, "").strip()

    if not value:
        return default

    try:
        parsed = int(value)
    except ValueError:
        return default

    return max(1, parsed)


def _env_positive_float(
    name: str,
    *,
    default: float,
) -> float:
    value = os.getenv(name, "").strip()

    if not value:
        return default

    try:
        parsed = float(value)
    except ValueError:
        return default

    return max(1.0, parsed)


JSON_CORRECTION_ATTEMPTS = _env_positive_int(
    "LLM_JSON_ATTEMPTS",
    default=2,
)

API_RETRY_ATTEMPTS = _env_positive_int(
    "LLM_API_RETRIES",
    default=3,
)

REQUEST_TIMEOUT_SECONDS = _env_positive_float(
    "LLM_REQUEST_TIMEOUT_SECONDS",
    default=120.0,
)

REASONING_TOKEN_HEADROOM = _env_positive_int(
    "LLM_REASONING_TOKEN_HEADROOM",
    default=2000,
)

MIN_REASONING_COMPLETION_TOKENS = _env_positive_int(
    "LLM_MIN_REASONING_COMPLETION_TOKENS",
    default=4000,
)

DEBUG_TIMING = _env_flag(
    "LLM_DEBUG_TIMING",
    default=False,
)


def _debug(message: str) -> None:
    if DEBUG_TIMING:
        print(
            f"[LLM] {message}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Model catalogue
# ---------------------------------------------------------------------------

MODEL_OPTIONS: dict[str, str] = {
    # OpenAI GPT-5.6 family.
    "OpenAI — GPT-5.6 Sol (strongest)": (
        "openai/gpt-5.6-sol"
    ),
    "OpenAI — GPT-5.6 Terra (balanced)": (
        "openai/gpt-5.6-terra"
    ),
    "OpenAI — GPT-5.6 Luna (lower cost)": (
        "openai/gpt-5.6-luna"
    ),

    "OpenAI — GPT-5.4 mini": (
        "openai/gpt-5.4-mini"
    ),

    # Stable fallbacks.
    "OpenAI — GPT-5 mini": (
        "openai/gpt-5-mini"
    ),
    "OpenAI — GPT-4.1 mini": (
        "openai/gpt-4.1-mini"
    ),
    "OpenAI — GPT-4o mini": (
        "openai/gpt-4o-mini"
    ),

    # Optional other providers.
    "Anthropic — Claude Sonnet 4.5": (
        "anthropic/claude-sonnet-4-5-20250929"
    ),
    "Google — Gemini 2.5 Pro": (
        "gemini/gemini-2.5-pro"
    ),
    "Google — Gemini 2.5 Flash": (
        "gemini/gemini-2.5-flash"
    ),
}

_DEFAULT_MODEL = os.getenv(
    "MODEL",
    "openai/gpt-4o-mini",
)

_RUNTIME_MODELS: dict[str, str] = {
    "analysis": os.getenv(
        "ANALYSIS_MODEL",
        _DEFAULT_MODEL,
    ),
    "chat": os.getenv(
        "CHAT_MODEL",
        _DEFAULT_MODEL,
    ),
}

_LAST_CALL_METADATA: dict[str, Any] = {}

_REWRITE_MARKERS = (
    "here is a rewritten",
    "improved version:",
)


# ---------------------------------------------------------------------------
# Public model-selection helpers
# ---------------------------------------------------------------------------

def get_model_options() -> dict[str, str]:
    """Return a copy of the user-facing model catalogue."""
    return dict(MODEL_OPTIONS)


def get_model_label(model_id: str) -> str:
    """Return the display label for a model ID, or the ID itself."""
    for label, candidate_id in MODEL_OPTIONS.items():
        if candidate_id == model_id:
            return label

    return model_id


def resolve_model(model_or_label: str) -> str:
    """
    Resolve either a user-facing label or a provider-prefixed model ID.

    Custom IDs are allowed even if they are not shown in MODEL_OPTIONS.
    """
    cleaned = str(
        model_or_label or ""
    ).strip()

    if not cleaned:
        raise ValueError(
            "Model selection cannot be empty."
        )

    if cleaned in MODEL_OPTIONS:
        return MODEL_OPTIONS[cleaned]

    valid_prefixes = (
        "openai/",
        "anthropic/",
        "gemini/",
        "ollama/",
    )

    if cleaned.startswith(valid_prefixes):
        return cleaned

    raise ValueError(
        "Unsupported model route. Expected a model label or "
        "a provider-prefixed ID beginning with openai/, "
        "anthropic/, gemini/, or ollama/."
    )


def set_runtime_model(
    model_or_label: str,
    *,
    route: RouteName = "analysis",
) -> str:
    """Set and return the active runtime model for one route."""
    if route not in _RUNTIME_MODELS:
        raise ValueError(
            f"Unknown LLM route: {route!r}."
        )

    resolved = resolve_model(
        model_or_label
    )

    _RUNTIME_MODELS[route] = resolved
    return resolved


def get_active_model(
    route: RouteName = "analysis",
) -> str:
    """Return the currently active model ID for a route."""
    if route not in _RUNTIME_MODELS:
        raise ValueError(
            f"Unknown LLM route: {route!r}."
        )

    return _RUNTIME_MODELS[route]


def get_last_call_metadata() -> dict[str, Any]:
    """Return metadata captured from the most recent LLM response."""
    return deepcopy(
        _LAST_CALL_METADATA
    )


# ---------------------------------------------------------------------------
# Provider and capability helpers
# ---------------------------------------------------------------------------

def _is_ollama(model: str) -> bool:
    return model.startswith(
        "ollama/"
    )


def _is_openai_reasoning_model(
    model: str,
) -> bool:
    """
    Return True for OpenAI GPT-5 and o-series reasoning routes.

    This includes GPT-5.6 Sol, Terra, and Luna because all begin with
    the provider-prefixed "openai/gpt-5" pattern.
    """
    return model.startswith(
        (
            "openai/gpt-5",
            "openai/o1",
            "openai/o3",
            "openai/o4",
            "gpt-5",
            "o1",
            "o3",
            "o4",
        )
    )


def _supports_reasoning_effort(
    model: str,
) -> bool:
    """Only send reasoning_effort to known OpenAI reasoning families."""
    return _is_openai_reasoning_model(
        model
    )


def _supports_temperature(
    model: str,
) -> bool:
    """
    Use the app's temperature only for non-reasoning models.

    Reasoning models use reasoning_effort and provider defaults.
    """
    return not _is_openai_reasoning_model(
        model
    )


def _supports_seed(
    model: str,
) -> bool:
    """Send the seed hint only to non-reasoning OpenAI models."""
    return (
        model.startswith("openai/")
        and not _is_openai_reasoning_model(
            model
        )
    )


def _required_api_key(
    model: str,
) -> str | None:
    if model.startswith("openai/"):
        return "OPENAI_API_KEY"

    if model.startswith("anthropic/"):
        return "ANTHROPIC_API_KEY"

    if model.startswith("gemini/"):
        return "GEMINI_API_KEY"

    if model.startswith("ollama/"):
        return None

    return None


def _raise_auth_error(
    model: str,
    exc: Exception,
) -> None:
    variable = _required_api_key(
        model
    )

    if variable is None:
        message = (
            "Authentication failed for model route "
            f"{model!r}."
        )
    else:
        message = (
            f"{variable} is invalid or missing for route "
            f"{model!r}. Check .env locally or Streamlit "
            "secrets after deployment."
        )

    raise RuntimeError(
        message
    ) from exc


def _raise_model_not_available(
    model: str,
    exc: Exception,
) -> None:
    if model.startswith("openai/"):
        detail = (
            "All OpenAI text models use the same OPENAI_API_KEY. "
            "This normally means the model ID is unavailable to "
            "the current API project, billing/tier access is missing, "
            "or the installed OpenAI/LiteLLM packages are too old."
        )
    else:
        detail = (
            "The provider did not recognise the model ID or the "
            "current account does not have access to it."
        )

    raise RuntimeError(
        f"Model {model!r} is not available. {detail}"
    ) from exc


def _route_reasoning_effort(
    route: RouteName,
    explicit_value: str | None,
) -> str | None:
    if explicit_value:
        return explicit_value.strip() or None

    route_key = (
        "ANALYSIS_REASONING_EFFORT"
        if route == "analysis"
        else "CHAT_REASONING_EFFORT"
    )

    configured = (
        os.getenv(route_key)
        or os.getenv("REASONING_EFFORT")
        or ""
    ).strip()

    return configured or None


def _route_seed(
    model: str,
    explicit_seed: int | None,
) -> int | None:
    if not _supports_seed(model):
        return None

    if explicit_seed is not None:
        return int(explicit_seed)

    configured = os.getenv(
        "LLM_SEED",
        "",
    ).strip()

    if not configured:
        return None

    try:
        return int(configured)
    except ValueError:
        return None


def _reasoning_completion_budget(
    requested_visible_tokens: int,
) -> int:
    """
    Give reasoning models room for both hidden reasoning and visible output.

    max_completion_tokens covers both categories, so passing the caller's
    visible-output target unchanged can leave no room for returned JSON.
    """
    return max(
        requested_visible_tokens
        + REASONING_TOKEN_HEADROOM,
        MIN_REASONING_COMPLETION_TOKENS,
    )


# ---------------------------------------------------------------------------
# Request construction and response parsing
# ---------------------------------------------------------------------------

def _call_kwargs(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    expect_json: bool,
    route: RouteName,
    reasoning_effort: str | None,
    seed: int | None,
) -> dict[str, Any]:
    """Build LiteLLM completion() keyword arguments."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "drop_params": True,
        "timeout": REQUEST_TIMEOUT_SECONDS,
    }

    if _supports_temperature(model):
        kwargs["temperature"] = temperature

    if _is_ollama(model):
        kwargs["api_base"] = os.getenv(
            "OLLAMA_API_BASE",
            "http://localhost:11434",
        )
    else:
        if _is_openai_reasoning_model(model):
            kwargs["max_completion_tokens"] = (
                _reasoning_completion_budget(
                    max_tokens
                )
            )
        else:
            kwargs["max_tokens"] = max_tokens

        if expect_json:
            kwargs["response_format"] = {
                "type": "json_object",
            }

    selected_reasoning = (
        _route_reasoning_effort(
            route,
            reasoning_effort,
        )
    )

    if (
        selected_reasoning
        and _supports_reasoning_effort(model)
    ):
        kwargs["reasoning_effort"] = (
            selected_reasoning
        )

    selected_seed = _route_seed(
        model,
        seed,
    )

    if selected_seed is not None:
        kwargs["seed"] = selected_seed

    return kwargs


def _strip_fences(
    text: str,
) -> str:
    """Remove leading and trailing Markdown code fences."""
    cleaned = str(
        text or ""
    ).strip()

    if cleaned.startswith("```"):
        newline = cleaned.find("\n")

        cleaned = (
            cleaned[newline + 1 :]
            if newline != -1
            else cleaned[3:]
        )

    if cleaned.endswith("```"):
        cleaned = cleaned[
            : cleaned.rfind("```")
        ].rstrip()

    return cleaned


def _extract_message_text(
    message: Any,
) -> str:
    """
    Extract visible text from string or content-block responses.

    Some providers return content as blocks rather than one string.
    """
    content = getattr(
        message,
        "content",
        None,
    )

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []

        for item in content:
            if isinstance(item, dict):
                value = (
                    item.get("text")
                    or item.get("content")
                    or ""
                )
            else:
                value = (
                    getattr(item, "text", None)
                    or getattr(item, "content", None)
                    or ""
                )

            if value:
                parts.append(str(value))

        return "\n".join(parts)

    return ""


def _parse_json(
    text: str,
) -> dict:
    """
    Parse the first JSON object in text.

    This tolerates a short preamble or accidental trailing prose.
    """
    start = text.find("{")

    if start != -1:
        parsed, _ = json.JSONDecoder().raw_decode(
            text,
            start,
        )

        if not isinstance(parsed, dict):
            raise json.JSONDecodeError(
                "Top-level JSON value must be an object",
                text,
                start,
            )

        return parsed

    parsed = json.loads(text)

    if not isinstance(parsed, dict):
        raise json.JSONDecodeError(
            "Top-level JSON value must be an object",
            text,
            0,
        )

    return parsed


def _check_no_rewrite(
    data: object,
    path: str = "",
) -> None:
    """Raise when a returned JSON field contains an anti-rewrite marker."""
    if isinstance(data, dict):
        for key, value in data.items():
            child_path = (
                f"{path}.{key}"
                if path
                else str(key)
            )

            _check_no_rewrite(
                value,
                child_path,
            )

    elif isinstance(data, list):
        for index, item in enumerate(data):
            _check_no_rewrite(
                item,
                f"{path}[{index}]",
            )

    elif isinstance(data, str):
        lowered = data.lower()

        for marker in _REWRITE_MARKERS:
            if marker in lowered:
                raise RuntimeError(
                    "Anti-rewrite rule violation in "
                    f"field {path!r}: found {marker!r}."
                )


def _serialise_usage(
    usage: Any,
) -> Any:
    if usage is None:
        return None

    if isinstance(usage, dict):
        return usage

    model_dump = getattr(
        usage,
        "model_dump",
        None,
    )

    if callable(model_dump):
        try:
            return model_dump()
        except Exception:
            pass

    return repr(usage)


def _record_response_metadata(
    *,
    response: Any,
    route: RouteName,
    requested_model: str,
    elapsed_seconds: float,
) -> None:
    """Store lightweight response metadata for debugging."""
    global _LAST_CALL_METADATA

    choices = getattr(
        response,
        "choices",
        [],
    ) or []

    first_choice = (
        choices[0]
        if choices
        else None
    )

    _LAST_CALL_METADATA = {
        "route": route,
        "requested_model": requested_model,
        "response_model": getattr(
            response,
            "model",
            None,
        ),
        "system_fingerprint": getattr(
            response,
            "system_fingerprint",
            None,
        ),
        "created": getattr(
            response,
            "created",
            None,
        ),
        "finish_reason": getattr(
            first_choice,
            "finish_reason",
            None,
        ),
        "usage": _serialise_usage(
            getattr(
                response,
                "usage",
                None,
            )
        ),
        "elapsed_seconds": round(
            elapsed_seconds,
            3,
        ),
    }


def _empty_response_error(
    *,
    response: Any,
    selected_model: str,
) -> RuntimeError:
    choices = getattr(
        response,
        "choices",
        [],
    ) or []

    choice = (
        choices[0]
        if choices
        else None
    )

    message = getattr(
        choice,
        "message",
        None,
    )

    finish_reason = getattr(
        choice,
        "finish_reason",
        None,
    )

    refusal = getattr(
        message,
        "refusal",
        None,
    )

    usage = _serialise_usage(
        getattr(
            response,
            "usage",
            None,
        )
    )

    guidance = ""

    if finish_reason == "length":
        guidance = (
            " The completion budget was exhausted. "
            "Increase LLM_REASONING_TOKEN_HEADROOM or "
            "LLM_MIN_REASONING_COMPLETION_TOKENS, or reduce "
            "the selected reasoning effort."
        )

    return RuntimeError(
        "The LLM returned no visible text. "
        f"Model: {selected_model}. "
        f"Finish reason: {finish_reason!r}. "
        f"Refusal: {refusal!r}. "
        f"Usage: {usage!r}."
        f"{guidance}"
    )


# ---------------------------------------------------------------------------
# Completion execution
# ---------------------------------------------------------------------------

def _run_completion_with_retries(
    *,
    kwargs: dict[str, Any],
    route: RouteName,
    requested_model: str,
) -> Any:
    """Run a LiteLLM request with bounded rate-limit retries."""
    for attempt in range(
        API_RETRY_ATTEMPTS
    ):
        started_at = time.perf_counter()

        try:
            response = completion(
                **kwargs
            )

            elapsed_seconds = (
                time.perf_counter()
                - started_at
            )

            _record_response_metadata(
                response=response,
                route=route,
                requested_model=requested_model,
                elapsed_seconds=elapsed_seconds,
            )

            _debug(
                "model="
                f"{requested_model} "
                f"route={route} "
                f"api_attempt={attempt + 1}/"
                f"{API_RETRY_ATTEMPTS} "
                f"elapsed={elapsed_seconds:.2f}s "
                f"token_parameter="
                f"{'max_completion_tokens' if 'max_completion_tokens' in kwargs else 'max_tokens'} "
                f"token_budget="
                f"{kwargs.get('max_completion_tokens', kwargs.get('max_tokens'))}"
            )

            return response

        except litellm.RateLimitError as exc:
            elapsed_seconds = (
                time.perf_counter()
                - started_at
            )

            if attempt < API_RETRY_ATTEMPTS - 1:
                sleep_seconds = 2 ** attempt

                _debug(
                    "rate_limit "
                    f"model={requested_model} "
                    f"elapsed={elapsed_seconds:.2f}s "
                    f"sleep={sleep_seconds}s"
                )

                time.sleep(sleep_seconds)
                continue

            raise RuntimeError(
                "Rate limit exceeded after "
                f"{API_RETRY_ATTEMPTS} attempts."
            ) from exc

        except litellm.AuthenticationError as exc:
            _raise_auth_error(
                requested_model,
                exc,
            )

        except litellm.APIConnectionError as exc:
            if _is_ollama(requested_model):
                api_base = os.getenv(
                    "OLLAMA_API_BASE",
                    "http://localhost:11434",
                )

                raise RuntimeError(
                    f"Cannot reach Ollama at {api_base}. "
                    "Is `ollama serve` running?"
                ) from exc

            raise RuntimeError(
                f"API connection error: {exc}"
            ) from exc

        except Exception as exc:
            message = str(exc).lower()

            if (
                "model_not_found" in message
                or "does not exist" in message
                or "unknown model" in message
                or (
                    "model" in message
                    and "not found" in message
                )
            ):
                _raise_model_not_available(
                    requested_model,
                    exc,
                )

            if (
                "max_completion_tokens" in message
                and (
                    "unexpected" in message
                    or "unsupported" in message
                    or "unknown" in message
                    or "unrecognized" in message
                )
            ):
                raise RuntimeError(
                    "The installed LiteLLM/OpenAI packages do not "
                    "appear to support max_completion_tokens for "
                    f"{requested_model!r}. Upgrade them with: "
                    "python -m pip install --upgrade litellm openai"
                ) from exc

            if (
                _is_ollama(requested_model)
                and "not found" in message
            ):
                model_name = (
                    requested_model.removeprefix(
                        "ollama/"
                    )
                )

                raise RuntimeError(
                    f"Ollama model {model_name!r} "
                    "was not found. Run: "
                    f"ollama pull {model_name}"
                ) from exc

            raise

    raise RuntimeError(
        "LLM request exhausted all retry attempts."
    )


# ---------------------------------------------------------------------------
# Public LLM API
# ---------------------------------------------------------------------------

def ask_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 1500,
    route: RouteName = "analysis",
    model: str | None = None,
    reasoning_effort: str | None = None,
    seed: int | None = None,
) -> dict:
    """
    Send a system/user request and return a parsed JSON object.

    Existing calls remain compatible because all new parameters are optional.
    """
    selected_model = (
        resolve_model(model)
        if model
        else get_active_model(route)
    )

    messages: list[
        dict[str, str]
    ] = [
        {
            "role": "system",
            "content": system,
        },
        {
            "role": "user",
            "content": user,
        },
    ]

    last_raw = ""

    for json_attempt in range(
        JSON_CORRECTION_ATTEMPTS
    ):
        kwargs = _call_kwargs(
            model=selected_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            expect_json=True,
            route=route,
            reasoning_effort=reasoning_effort,
            seed=seed,
        )

        response = _run_completion_with_retries(
            kwargs=kwargs,
            route=route,
            requested_model=selected_model,
        )

        choices = getattr(
            response,
            "choices",
            [],
        ) or []

        if not choices:
            raise RuntimeError(
                "The LLM response contained no choices. "
                f"Model: {selected_model}."
            )

        choice = choices[0]
        message = getattr(
            choice,
            "message",
            None,
        )

        raw = _strip_fences(
            _extract_message_text(message)
        )

        last_raw = raw

        # Do not spend another full request retrying an empty response.
        if not raw:
            raise _empty_response_error(
                response=response,
                selected_model=selected_model,
            )

        try:
            parsed = _parse_json(raw)

        except json.JSONDecodeError as exc:
            _debug(
                "invalid_json "
                f"model={selected_model} "
                f"json_attempt={json_attempt + 1}/"
                f"{JSON_CORRECTION_ATTEMPTS} "
                f"raw_length={len(raw)} "
                f"finish_reason="
                f"{getattr(choice, 'finish_reason', None)!r}"
            )

            if (
                json_attempt
                < JSON_CORRECTION_ATTEMPTS - 1
            ):
                snippet = raw[
                    max(0, exc.pos - 20) :
                    exc.pos + 80
                ]

                messages.append(
                    {
                        "role": "assistant",
                        "content": raw,
                    }
                )

                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous output could not be "
                            "parsed as JSON.\n"
                            f"Error: {exc.msg} at position "
                            f"{exc.pos}.\n"
                            f"Near: {snippet!r}\n\n"
                            "Return only one corrected JSON "
                            "object with no Markdown fences "
                            "and no explanatory text."
                        ),
                    }
                )

                continue

            raise RuntimeError(
                "LLM returned invalid JSON after "
                f"{json_attempt + 1} attempts. "
                f"Model: {selected_model}. "
                f"Raw prefix: {raw[:300]}"
            ) from exc

        _check_no_rewrite(parsed)

        return parsed

    raise RuntimeError(
        "ask_json exhausted all JSON-correction "
        f"attempts. Raw prefix: {last_raw[:300]}"
    )


def ask_text(
    system: str,
    user: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 600,
    route: RouteName = "analysis",
    model: str | None = None,
    reasoning_effort: str | None = None,
    seed: int | None = None,
) -> str:
    """
    Send a system/user request and return plain text.

    Use route="chat" for chatbot calls that should use the chat selector.
    """
    selected_model = (
        resolve_model(model)
        if model
        else get_active_model(route)
    )

    messages: list[
        dict[str, str]
    ] = [
        {
            "role": "system",
            "content": system,
        },
        {
            "role": "user",
            "content": user,
        },
    ]

    kwargs = _call_kwargs(
        model=selected_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        expect_json=False,
        route=route,
        reasoning_effort=reasoning_effort,
        seed=seed,
    )

    response = _run_completion_with_retries(
        kwargs=kwargs,
        route=route,
        requested_model=selected_model,
    )

    choices = getattr(
        response,
        "choices",
        [],
    ) or []

    if not choices:
        raise RuntimeError(
            "The LLM response contained no choices. "
            f"Model: {selected_model}."
        )

    message = getattr(
        choices[0],
        "message",
        None,
    )

    text = _extract_message_text(
        message
    ).strip()

    if not text:
        raise _empty_response_error(
            response=response,
            selected_model=selected_model,
        )

    return text
