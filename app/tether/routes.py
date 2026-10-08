import json
import urllib.error
import urllib.request
from functools import lru_cache

import anthropic
from flask import Blueprint, Response, jsonify, request, stream_with_context

from ..config import Config
from ..stores import get_store
from .prompt import context_message, patient_label, system_prompt

bp = Blueprint("tether", __name__, url_prefix="/api/tether")

ROLES = {"user", "assistant", "system"}
MAX_TOKENS = 16000  # cost cap per reply; thinking counts toward it


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)


def _event(name: str, data) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


def _echoable(content: list) -> list[dict]:
    """Content blocks as the client must replay them next turn.

    After a mid-output server-side fallback, model-internal blocks before the last
    ``fallback`` marker belong to the model that declined and must not be echoed.
    """
    blocks = [b.model_dump(mode="json", exclude_none=True) for b in content]
    last = max((i for i, b in enumerate(blocks) if b["type"] == "fallback"), default=-1)
    return [
        b for i, b in enumerate(blocks)
        if b["type"] != "fallback" and not (i < last and b["type"] in ("thinking", "redacted_thinking"))
    ]


@bp.get("/health")
def health():
    return jsonify(
        configured=bool(Config.ANTHROPIC_API_KEY),
        model=Config.TETHER_MODEL,
        patient=patient_label(get_store()),
        tts=bool(Config.ELEVENLABS_API_KEY),
    )


@bp.post("/speak")
def speak():
    """Proxy reply text to ElevenLabs text-to-speech and stream the mp3 back."""
    if not Config.ELEVENLABS_API_KEY:
        return jsonify(error="ELEVENLABS_API_KEY is not set"), 503
    text = str((request.get_json(silent=True) or {}).get("text") or "").strip()[:5000]
    if not text:
        return jsonify(error="text is required"), 400
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{Config.ELEVENLABS_VOICE_ID}/stream?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": Config.ELEVENLABS_MODEL_ID}).encode(),
        headers={"xi-api-key": Config.ELEVENLABS_API_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        upstream = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        return jsonify(error=f"ElevenLabs error {e.code}: {e.read(500).decode(errors='replace')}"), 502
    except urllib.error.URLError as e:
        return jsonify(error=f"Could not reach ElevenLabs: {e.reason}"), 502

    def generate():
        with upstream:
            while chunk := upstream.read(16384):
                yield chunk

    return Response(stream_with_context(generate()), mimetype="audio/mpeg", headers={"Cache-Control": "no-cache"})


@bp.post("/chat")
def chat():
    """Stream one assistant turn as server-sent events.

    Body: {"messages": [...]} - the full conversation so far, as Messages API message
    objects, ending with the new user message. The server is stateless; the client keeps
    the history and must echo assistant turns back exactly as the ``done`` event gave them
    (thinking blocks included), and keep the ``context`` system message in place.

    Events: ``context`` (system message injected on the first turn), ``text`` (delta),
    ``done`` (full content blocks + stop info), ``error``.
    """
    if not Config.ANTHROPIC_API_KEY:
        return jsonify(error="ANTHROPIC_API_KEY is not set"), 503
    body = request.get_json(silent=True) or {}
    messages = body.get("messages")
    valid = (
        isinstance(messages, list)
        and messages
        and all(isinstance(m, dict) and m.get("role") in ROLES and m.get("content") for m in messages)
        and messages[-1]["role"] == "user"
    )
    if not valid:
        return jsonify(error="messages must be a non-empty list ending with a user message"), 400

    injected = context_message(get_store()) if len(messages) == 1 else None
    if injected:
        messages = messages + [injected]

    def generate():
        if injected:
            yield _event("context", injected)
        try:
            with get_client().beta.messages.stream(
                model=Config.TETHER_MODEL,
                max_tokens=MAX_TOKENS,
                system=[{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}],
                messages=messages,
                output_config={"effort": Config.TETHER_EFFORT},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                for text in stream.text_stream:
                    yield _event("text", text)
                final = stream.get_final_message()
        except anthropic.RateLimitError:
            yield _event("error", {"error": "Rate limited; try again in a moment."})
            return
        except anthropic.APIStatusError as e:
            yield _event("error", {"error": f"API error {e.status_code}: {e.message}"})
            return
        except anthropic.APIConnectionError:
            yield _event("error", {"error": "Could not reach the API."})
            return

        done = {
            "content": _echoable(final.content),
            "stop_reason": final.stop_reason,
            "model": final.model,
            "usage": {
                "input_tokens": final.usage.input_tokens,
                "output_tokens": final.usage.output_tokens,
                "cache_read_input_tokens": final.usage.cache_read_input_tokens,
            },
        }
        if final.stop_reason == "refusal" and final.stop_details:
            done["refusal"] = {
                "category": final.stop_details.category,
                "explanation": final.stop_details.explanation,
            }
        yield _event("done", done)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
