"""Tests for the AI service layer, the scanner and the assistant failure handling."""
import io
from types import SimpleNamespace
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from assistant.models import AIConversation, AIMessage
from core.testing import make_curriculum, make_user
from scanner.models import ScannerHistory
from scanner.services import SCAN_SCHEMA

from . import ai_service


def png_upload(name="q.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class ProviderSelectionMixin:
    def setUp(self):
        ai_service.reset_provider_cache()
        self.addCleanup(ai_service.reset_provider_cache)


@override_settings(AI_PROVIDER="disabled")
class DisabledProviderTests(ProviderSelectionMixin, TestCase):
    def test_disabled_provider_raises_friendly_error(self):
        with self.assertRaises(ai_service.AIServiceError) as ctx:
            ai_service.chat("system", [{"role": "user", "content": "hi"}])
        self.assertIn("not configured", ctx.exception.user_message)

    def test_scanner_api_returns_503_and_records_failure(self):
        user = make_user()
        self.client.force_login(user)
        r = self.client.post(reverse("api:scanner-list"), {"question": "What is 2+2?"})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"]["code"], "ai_unavailable")
        self.assertEqual(ScannerHistory.objects.get(user=user).status, ScannerHistory.Status.FAILED)

    def test_assistant_failure_rolls_back_student_message(self):
        user = make_user()
        self.client.force_login(user)
        conv = AIConversation.objects.create(user=user)
        r = self.client.post(reverse("api:conversation-messages", args=[conv.pk]), {"content": "Hello"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 503)
        self.assertFalse(AIMessage.objects.exists())


@override_settings(AI_PROVIDER="mock")
class MockProviderTests(ProviderSelectionMixin, TestCase):
    def test_structured_output_matches_schema_keys(self):
        data = ai_service.generate_json("s", "question", SCAN_SCHEMA)
        self.assertEqual(set(data), set(SCAN_SCHEMA["properties"]))
        self.assertTrue(data["is_question_found"])

    def test_scan_image_saves_history_for_user(self):
        make_curriculum()
        user = make_user()
        self.client.force_login(user)
        r = self.client.post(reverse("api:scanner-list"), {"image": png_upload()})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["status"], "completed")
        self.assertTrue(ScannerHistory.objects.get(user=user).image)

    def test_guest_scan_is_not_stored(self):
        r = self.client.post(reverse("api:scanner-list"), {"question": "Solve x + 1 = 2"})
        self.assertEqual(r.status_code, 201)
        self.assertFalse(ScannerHistory.objects.exists())

    def test_non_image_upload_rejected(self):
        fake = SimpleUploadedFile("evil.png", b"MZ\x90\x00not-an-image", content_type="image/png")
        r = self.client.post(reverse("api:scanner-list"), {"image": fake})
        self.assertEqual(r.status_code, 400)

    def test_assistant_conversation_flow(self):
        user = make_user()
        self.client.force_login(user)
        conv = self.client.post(reverse("api:conversation-list"), {"mode": "simple"},
                                content_type="application/json").json()
        r = self.client.post(reverse("api:conversation-messages", args=[conv["id"]]),
                             {"content": "What is photosynthesis?"}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["conversation"]["title"], "What is photosynthesis?")
        self.assertEqual(AIMessage.objects.count(), 2)

    def test_cannot_post_to_another_users_conversation(self):
        conv = AIConversation.objects.create(user=make_user("owner@example.com"))
        self.client.force_login(make_user())
        r = self.client.post(reverse("api:conversation-messages", args=[conv.pk]), {"content": "hi"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 404)


@override_settings(AI_PROVIDER="groq", AI_API_KEY="test-key", AI_MODEL="", AI_VISION_MODEL="",
                   AI_BASE_URL="")
class OpenAICompatibleProviderTests(ProviderSelectionMixin, TestCase):
    """Groq / OpenRouter path. The `openai` client is mocked — no network calls."""

    def _response(self, text, finish_reason="stop"):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=finish_reason)],
            model="llama-test", usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7))

    def test_groq_preset_fills_base_url_and_models(self):
        provider = ai_service.get_provider()
        self.assertEqual(str(provider.client.base_url).rstrip("/"), "https://api.groq.com/openai/v1")
        self.assertTrue(provider.model)
        self.assertTrue(provider.vision_model)
        self.assertTrue(ai_service.is_configured())

    def test_image_request_uses_vision_model_and_data_url(self):
        provider = ai_service.get_provider()
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}, "steps": {"type": "array",
                  "items": {"type": "string"}}}, "required": ["ok", "steps"], "additionalProperties": False}
        with mock.patch.object(provider.client.chat.completions, "create",
                               return_value=self._response('```json\n{"ok": "true"}\n```')) as create:
            data = ai_service.generate_json("system", [ai_service.image_block(b"\x89PNG", "image/png"),
                                                       ai_service.text_block("solve")], schema)
        # Missing keys are filled and types coerced to the schema.
        self.assertEqual(data, {"ok": True, "steps": []})
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["model"], provider.vision_model)
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})
        self.assertEqual(kwargs["messages"][0]["role"], "system")
        image = kwargs["messages"][1]["content"][0]
        self.assertTrue(image["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_chat_uses_text_model(self):
        provider = ai_service.get_provider()
        with mock.patch.object(provider.client.chat.completions, "create",
                               return_value=self._response("Photosynthesis is...")) as create:
            response = ai_service.chat("s", [{"role": "user", "content": "What is photosynthesis?"}])
        self.assertEqual(response.text, "Photosynthesis is...")
        self.assertEqual(create.call_args.kwargs["model"], provider.model)
        self.assertEqual(response.input_tokens, 12)

    def test_auth_error_is_friendly_and_not_retryable(self):
        import httpx2 as httpx  # the openai SDK in use is built on httpx2
        import openai

        provider = ai_service.get_provider()
        request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        error = openai.AuthenticationError("bad key", response=httpx.Response(401, request=request), body=None)
        with mock.patch.object(provider.client.chat.completions, "create", side_effect=error):
            with self.assertRaises(ai_service.AIServiceError) as ctx:
                ai_service.chat("s", [{"role": "user", "content": "x"}])
        self.assertFalse(ctx.exception.retryable)
        self.assertEqual(ctx.exception.user_message, ai_service.DEFAULT_UNAVAILABLE)

    @override_settings(AI_API_KEY="")
    def test_missing_key_disables_ai_gracefully(self):
        ai_service.reset_provider_cache()
        self.assertIsInstance(ai_service.get_provider(), ai_service.DisabledProvider)
        self.assertFalse(ai_service.is_configured())


@override_settings(AI_PROVIDER="anthropic", AI_API_KEY="test-key", AI_MODEL="claude-opus-5",
                   AI_REFUSAL_FALLBACK=True, AI_EFFORT="")
class AnthropicProviderTests(ProviderSelectionMixin, TestCase):
    """The SDK client is mocked — no network calls."""

    def _response(self, text='{"ok": true}', stop_reason="end_turn"):
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason,
            model="claude-opus-5", usage=SimpleNamespace(input_tokens=10, output_tokens=5))

    def test_request_shape_with_image_and_schema(self):
        provider = ai_service.get_provider()
        with mock.patch.object(provider.client.beta.messages, "create",
                               return_value=self._response()) as create:
            data = ai_service.generate_json(
                "system", [ai_service.image_block(b"\x89PNG", "image/png"), ai_service.text_block("solve")],
                {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
                 "additionalProperties": False})
        self.assertEqual(data, {"ok": True})
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5")
        self.assertEqual(kwargs["fallbacks"], "default")
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")
        image = kwargs["messages"][0]["content"][0]
        self.assertEqual(image["type"], "image")
        self.assertEqual(image["source"]["media_type"], "image/png")

    def test_refusal_becomes_non_retryable_error(self):
        provider = ai_service.get_provider()
        with mock.patch.object(provider.client.beta.messages, "create",
                               return_value=self._response("", stop_reason="refusal")):
            with self.assertRaises(ai_service.AIServiceError) as ctx:
                ai_service.chat("s", [{"role": "user", "content": "x"}])
        self.assertFalse(ctx.exception.retryable)

    def test_connection_error_becomes_friendly_error(self):
        import anthropic
        import httpx2

        provider = ai_service.get_provider()
        error = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))
        with mock.patch.object(provider.client.beta.messages, "create", side_effect=error):
            with self.assertRaises(ai_service.AIServiceError) as ctx:
                ai_service.chat("s", [{"role": "user", "content": "x"}])
        self.assertTrue(ctx.exception.retryable)
        self.assertEqual(ctx.exception.user_message, ai_service.DEFAULT_UNAVAILABLE)
