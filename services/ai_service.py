"""
AI service layer.

Views and app services never call an AI SDK directly — they use the
functions at the bottom of this module (`chat`, `generate_json`,
`is_configured`). The concrete provider is chosen by `AI_PROVIDER`:

* ``anthropic`` — Claude via the official Anthropic SDK (default)
* ``groq`` / ``openrouter`` / ``openai_compatible`` — any OpenAI-compatible
  Chat Completions API (via the `openai` SDK and `AI_BASE_URL`)
* ``mock``      — deterministic offline responses for development/tests
* ``disabled``  — every call raises AIServiceError (friendly UI message)

Adding another provider = subclass `BaseAIProvider` and register it in
`_PROVIDERS`. API keys come only from environment variables.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger("prepai.ai")

DEFAULT_UNAVAILABLE = "AI service is temporarily unavailable. Please try again."


class AIServiceError(Exception):
    """Raised for any AI failure. `user_message` is safe to show to students."""

    def __init__(self, message, user_message=DEFAULT_UNAVAILABLE, retryable=True):
        super().__init__(message)
        self.user_message = user_message
        self.retryable = retryable


@dataclass
class AIResponse:
    text: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    data: dict | None = field(default=None)


# ---------------------------------------------------------------------------
# Provider-neutral message format
#   messages = [{"role": "user"|"assistant", "content": str | [block, ...]}]
#   block    = {"type": "text", "text": str}
#            | {"type": "image", "media_type": "image/png", "data": <bytes>}
# ---------------------------------------------------------------------------
def text_block(text):
    return {"type": "text", "text": text}


def image_block(data: bytes, media_type: str):
    return {"type": "image", "media_type": media_type, "data": data}


class BaseAIProvider:
    name = "base"

    def complete(self, *, system: str, messages: list, max_tokens: int | None = None,
                 json_schema: dict | None = None) -> AIResponse:
        raise NotImplementedError


class DisabledProvider(BaseAIProvider):
    name = "disabled"

    def complete(self, **kwargs):
        raise AIServiceError(
            "AI provider is disabled",
            user_message="AI features are not configured on this server yet.",
            retryable=False,
        )


class AnthropicProvider(BaseAIProvider):
    """Claude via the official `anthropic` Python SDK."""

    name = "anthropic"
    # Models that support server-side refusal fallbacks (beta).
    _FALLBACK_MODELS = ("claude-opus-5", "claude-fable-5-1")
    _FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(self):
        import anthropic

        self._anthropic = anthropic
        try:
            self.client = anthropic.Anthropic(
                api_key=settings.AI_API_KEY or None,  # None → SDK resolves ANTHROPIC_API_KEY etc.
                timeout=float(settings.AI_TIMEOUT),
                max_retries=2,
            )
        except anthropic.AnthropicError as exc:
            raise AIServiceError(f"Could not initialise Anthropic client: {exc}") from exc
        self.model = settings.AI_MODEL or "claude-opus-5"

    @staticmethod
    def _convert_content(content):
        if isinstance(content, str):
            return content
        blocks = []
        for block in content:
            if block["type"] == "image":
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": block["media_type"],
                        "data": base64.standard_b64encode(block["data"]).decode("ascii"),
                    },
                })
            else:
                blocks.append({"type": "text", "text": block["text"]})
        return blocks

    def complete(self, *, system, messages, max_tokens=None, json_schema=None):
        anthropic = self._anthropic
        request = {
            "model": self.model,
            "max_tokens": max_tokens or settings.AI_MAX_TOKENS,
            "system": system,
            "messages": [
                {"role": m["role"], "content": self._convert_content(m["content"])}
                for m in messages
            ],
        }
        output_config = {}
        if json_schema:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        if settings.AI_EFFORT:
            output_config["effort"] = settings.AI_EFFORT
        if output_config:
            request["output_config"] = output_config

        use_fallback = settings.AI_REFUSAL_FALLBACK and self.model in self._FALLBACK_MODELS
        try:
            if use_fallback:
                response = self.client.beta.messages.create(
                    betas=[self._FALLBACK_BETA], fallbacks="default", **request
                )
            else:
                response = self.client.messages.create(**request)
        except anthropic.AuthenticationError as exc:
            logger.error("Anthropic authentication failed — check AI_API_KEY: %s", exc)
            raise AIServiceError(str(exc), retryable=False) from exc
        except anthropic.PermissionDeniedError as exc:
            logger.error("Anthropic permission denied: %s", exc)
            raise AIServiceError(str(exc), retryable=False) from exc
        except anthropic.BadRequestError as exc:
            logger.error("Anthropic rejected the request: %s", exc)
            raise AIServiceError(
                str(exc), user_message="The AI couldn't process this request. "
                                       "Try rephrasing it or using a clearer image.",
                retryable=False,
            ) from exc
        except anthropic.RateLimitError as exc:
            logger.warning("Anthropic rate limit hit: %s", exc)
            raise AIServiceError(
                str(exc), user_message="The AI is busy right now. Please try again in a minute."
            ) from exc
        except anthropic.APIStatusError as exc:
            logger.warning("Anthropic API error %s: %s", exc.status_code, exc)
            raise AIServiceError(str(exc)) from exc
        except anthropic.APITimeoutError as exc:
            logger.warning("Anthropic request timed out")
            raise AIServiceError(
                str(exc), user_message="The AI took too long to respond. Please try again."
            ) from exc
        except anthropic.APIConnectionError as exc:
            logger.warning("Could not reach Anthropic: %s", exc)
            raise AIServiceError(str(exc)) from exc

        if response.stop_reason == "refusal":
            raise AIServiceError(
                "Model declined the request",
                user_message="PrepAI can't help with that request. "
                             "Please ask a study-related question.",
                retryable=False,
            )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason == "max_tokens" and json_schema:
            raise AIServiceError("Structured response was truncated (max_tokens)")
        if not text:
            raise AIServiceError("Empty response from model")

        data = None
        if json_schema:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise AIServiceError(f"Invalid JSON from model: {exc}") from exc

        usage = response.usage
        return AIResponse(
            text=text,
            model=response.model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            data=data,
        )


class OpenAICompatibleProvider(BaseAIProvider):
    """
    Any provider exposing the OpenAI Chat Completions API: Groq, OpenRouter,
    Together, a self-hosted vLLM/Ollama server, etc. Uses the official `openai`
    SDK pointed at `AI_BASE_URL`.

    Presets fill in the base URL and sensible default models; AI_MODEL /
    AI_VISION_MODEL override them. Model IDs change often — check your
    provider's model list if a request fails with "model not found".
    """

    name = "openai_compatible"
    PRESETS = {
        # preset: (base_url, default text model, default vision model)
        "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile",
                 "meta-llama/llama-4-scout-17b-16e-instruct"),
        "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct",
                       "meta-llama/llama-4-scout"),
        # xAI (Grok). No default model: xAI's lineup changes often, so set AI_MODEL
        # to an ID from GET https://api.x.ai/v1/models.
        "xai": ("https://api.x.ai/v1", "", ""),
    }

    def __init__(self, preset=None):
        import openai

        self._openai = openai
        base_url, default_model, default_vision = self.PRESETS.get(preset, ("", "", ""))
        base_url = settings.AI_BASE_URL or base_url
        if not base_url:
            raise AIServiceError("AI_BASE_URL is required for AI_PROVIDER=openai_compatible",
                                 retryable=False)
        if not settings.AI_API_KEY:
            raise AIServiceError("AI_API_KEY is not set", retryable=False)
        headers = {}
        if "openrouter.ai" in base_url:  # optional attribution headers OpenRouter recommends
            headers = {"HTTP-Referer": settings.SITE_URL, "X-Title": settings.SITE_NAME}
        self.client = openai.OpenAI(api_key=settings.AI_API_KEY, base_url=base_url,
                                    timeout=float(settings.AI_TIMEOUT), max_retries=2,
                                    default_headers=headers or None)
        self.model = settings.AI_MODEL or default_model
        if not self.model:
            raise AIServiceError("AI_MODEL is required for this provider", retryable=False)
        self.vision_model = settings.AI_VISION_MODEL or default_vision or self.model

    @staticmethod
    def _convert_content(content):
        if isinstance(content, str):
            return content
        parts = []
        for block in content:
            if block["type"] == "image":
                data = base64.standard_b64encode(block["data"]).decode("ascii")
                parts.append({"type": "image_url",
                              "image_url": {"url": f"data:{block['media_type']};base64,{data}"}})
            else:
                parts.append({"type": "text", "text": block["text"]})
        return parts

    @staticmethod
    def _has_image(messages):
        return any(isinstance(m["content"], list) and any(b["type"] == "image" for b in m["content"])
                   for m in messages)

    @classmethod
    def _conform(cls, value, schema):
        """Coerce parsed JSON to the schema's shape (these providers don't enforce schemas)."""
        kind = schema.get("type")
        if kind == "object":
            value = value if isinstance(value, dict) else {}
            return {k: cls._conform(value.get(k), sub) for k, sub in schema.get("properties", {}).items()}
        if kind == "array":
            items = value if isinstance(value, list) else ([] if value in (None, "") else [value])
            return [cls._conform(v, schema.get("items", {})) for v in items]
        if kind == "boolean":
            return value.strip().lower() in ("true", "yes", "1") if isinstance(value, str) else bool(value)
        if kind in ("integer", "number"):
            try:
                return int(value) if kind == "integer" else float(value)
            except (TypeError, ValueError):
                return 0
        return "" if value is None else (value if isinstance(value, str) else json.dumps(value))

    def complete(self, *, system, messages, max_tokens=None, json_schema=None):
        openai = self._openai
        if json_schema:
            system = (f"{system}\n\nRespond with ONLY a single JSON object (no markdown, no prose) "
                      f"that matches this JSON Schema:\n{json.dumps(json_schema)}")
        request = {
            "model": self.vision_model if self._has_image(messages) else self.model,
            "max_tokens": max_tokens or settings.AI_MAX_TOKENS,
            "messages": [{"role": "system", "content": system}] + [
                {"role": m["role"], "content": self._convert_content(m["content"])} for m in messages
            ],
        }
        if json_schema:
            request["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**request)
        except openai.AuthenticationError as exc:
            logger.error("AI provider authentication failed — check AI_API_KEY: %s", exc)
            raise AIServiceError(str(exc), retryable=False) from exc
        except openai.PermissionDeniedError as exc:
            logger.error("AI provider permission denied: %s", exc)
            raise AIServiceError(str(exc), retryable=False) from exc
        except openai.BadRequestError as exc:
            logger.error("AI provider rejected the request (check AI_MODEL / AI_VISION_MODEL): %s", exc)
            raise AIServiceError(
                str(exc), user_message="The AI couldn't process this request. "
                                       "Try rephrasing it or using a clearer image.",
                retryable=False,
            ) from exc
        except openai.RateLimitError as exc:
            logger.warning("AI provider rate limit hit: %s", exc)
            raise AIServiceError(
                str(exc), user_message="The AI is busy right now. Please try again in a minute."
            ) from exc
        except openai.APIStatusError as exc:
            logger.warning("AI provider error %s: %s", exc.status_code, exc)
            raise AIServiceError(str(exc)) from exc
        except openai.APITimeoutError as exc:
            logger.warning("AI provider request timed out")
            raise AIServiceError(
                str(exc), user_message="The AI took too long to respond. Please try again."
            ) from exc
        except openai.APIConnectionError as exc:
            logger.warning("Could not reach AI provider: %s", exc)
            raise AIServiceError(str(exc)) from exc

        if not response.choices:
            raise AIServiceError("Empty response from model")
        choice = response.choices[0]
        if choice.finish_reason == "content_filter":
            raise AIServiceError(
                "Model declined the request",
                user_message="PrepAI can't help with that request. "
                             "Please ask a study-related question.",
                retryable=False,
            )
        text = (choice.message.content or "").strip()
        if json_schema and choice.finish_reason == "length":
            raise AIServiceError("Structured response was truncated (max_tokens)")
        if not text:
            raise AIServiceError("Empty response from model")

        data = None
        if json_schema:
            cleaned = text
            if cleaned.startswith("```"):  # some models wrap JSON in a code fence anyway
                cleaned = cleaned.strip("`").removeprefix("json").strip()
            try:
                data = self._conform(json.loads(cleaned), json_schema)
            except json.JSONDecodeError as exc:
                raise AIServiceError(f"Invalid JSON from model: {exc}") from exc

        usage = getattr(response, "usage", None)
        return AIResponse(
            text=text,
            model=response.model or request["model"],
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            data=data,
        )


class MockProvider(BaseAIProvider):
    """
    Offline provider for local development and automated tests.
    Responses are clearly labelled and never presented as real AI output.
    """

    name = "mock"

    def complete(self, *, system, messages, max_tokens=None, json_schema=None):
        last = messages[-1]["content"] if messages else ""
        if not isinstance(last, str):
            last = " ".join(b.get("text", "") for b in last if b["type"] == "text")
        if json_schema:
            data = self._sample_from_schema(json_schema, last)
            return AIResponse(text=json.dumps(data), model="mock", data=data)
        text = (
            "**[Mock AI response — configure AI_PROVIDER=anthropic for real answers]**\n\n"
            f"You asked: *{last[:300]}*\n\n"
            "- In real mode, PrepAI explains the concept step by step.\n"
            "- It can also generate practice questions and quizzes."
        )
        return AIResponse(text=text, model="mock")

    def _sample_from_schema(self, schema, prompt, key=""):
        kind = schema.get("type")
        if kind == "object":
            return {k: self._sample_from_schema(v, prompt, k)
                    for k, v in schema.get("properties", {}).items()}
        if kind == "array":
            return [self._sample_from_schema(schema.get("items", {}), prompt, key)]
        if kind == "boolean":
            return key.startswith("is_question")  # e.g. is_question_found → True
        if kind in ("integer", "number"):
            return 0
        if "enum" in schema:
            return schema["enum"][0]
        return f"[Mock {key.replace('_', ' ')}]"


_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "groq": lambda: OpenAICompatibleProvider("groq"),
    "openrouter": lambda: OpenAICompatibleProvider("openrouter"),
    "xai": lambda: OpenAICompatibleProvider("xai"),
    "mock": MockProvider,
    "disabled": DisabledProvider,
}


@lru_cache(maxsize=1)
def get_provider() -> BaseAIProvider:
    name = (settings.AI_PROVIDER or "disabled").lower()
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        logger.error("Unknown AI_PROVIDER %r — AI disabled", name)
        return DisabledProvider()
    try:
        return provider_cls()
    except AIServiceError:
        logger.exception("AI provider %s failed to initialise — AI disabled", name)
        return DisabledProvider()


def reset_provider_cache():
    """Call after changing AI settings at runtime (used by tests)."""
    get_provider.cache_clear()


def is_configured() -> bool:
    """True when an AI provider is selected and credentials appear to be present."""
    name = (settings.AI_PROVIDER or "").lower()
    if name == "mock":
        return True
    if name == "anthropic":
        return bool(settings.AI_API_KEY or os.environ.get("ANTHROPIC_API_KEY")
                    or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if name in ("openai_compatible", "groq", "openrouter", "xai"):
        return bool(settings.AI_API_KEY)
    return False


# ---------------------------------------------------------------------------
# Public API used by app services
# ---------------------------------------------------------------------------
def chat(system: str, messages: list, max_tokens: int | None = None) -> AIResponse:
    """Free-form conversation turn."""
    return get_provider().complete(system=system, messages=messages, max_tokens=max_tokens)


def generate_json(system: str, content, schema: dict, max_tokens: int | None = None) -> dict:
    """Single-turn request whose response must match `schema`. Returns the parsed dict."""
    response = get_provider().complete(
        system=system,
        messages=[{"role": "user", "content": content}],
        max_tokens=max_tokens,
        json_schema=schema,
    )
    if not isinstance(response.data, dict):
        raise AIServiceError("Structured response missing")
    return response.data
