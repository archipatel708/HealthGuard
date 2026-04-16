from __future__ import annotations

import json
import os
import re
from typing import Any

import requests


class LLMTimeoutError(Exception):
    pass


def _llm_endpoint() -> str:
    return os.environ.get("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")


def _api_keys() -> list[str]:
    keys = [
        os.environ.get("OPENROUTER_API_KEY", "").strip(),
        os.environ.get("OPENROUTER_API_KEY_FALLBACK", "").strip(),
        os.environ.get("OPENROUTER_API_KEY_TERTIARY", "").strip(),
    ]
    return [key for key in keys if key]


def _models() -> list[str]:
    primary = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3-next-80b-a3b-instruct:free").strip()
    fallback = os.environ.get("OPENROUTER_MODEL_FALLBACK", "openai/gpt-oss-120b:free").strip()
    tertiary = os.environ.get("OPENROUTER_MODEL_TERTIARY", "").strip()
    models = [primary, fallback, tertiary]
    return [model for model in models if model]


def _post_with_fallback(messages: list[dict], temperature: float) -> str:
    had_timeout = False
    endpoint = _llm_endpoint()
    models = _models()
    keys = _api_keys()
    if not models or not keys:
        return ""

    for api_key in keys:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        for model in models:
            payload = {"model": model, "messages": messages, "temperature": temperature}
            try:
                response = requests.post(endpoint, json=payload, headers=headers, timeout=12)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except requests.Timeout:
                had_timeout = True
                continue
            except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
                continue

    if had_timeout:
        raise LLMTimeoutError("LLM timeout across fallback chain")
    return ""


def _extract_with_llm(text: str, symptoms_vocab: list[str], user_profile: dict) -> dict[str, Any]:
    if not _api_keys():
        return {}

    records = user_profile.get("abha_records", [])
    prompt = (
        "Extract JSON with keys symptoms (array), age (number|null), gender (string|null). "
        "Use only symptoms from allowed vocabulary."
    )
    messages = [
        {
            "role": "system",
            "content": f"{prompt}\nABHA context for this patient: {json.dumps(records)}",
        },
        {
            "role": "user",
            "content": f"Text: {text}\nAllowed symptoms vocabulary: {json.dumps(symptoms_vocab[:300])}",
        },
    ]

    try:
        content = _post_with_fallback(messages=messages, temperature=0.1)
    except LLMTimeoutError:
        raise
    except Exception:
        return {}

    if not content:
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def extract_structured_input(text: str, symptoms_vocab: list[str], user_profile: dict) -> dict[str, Any]:
    llm_result = _extract_with_llm(text=text, symptoms_vocab=symptoms_vocab, user_profile=user_profile)
    if llm_result and isinstance(llm_result.get("symptoms"), list):
        normalized = []
        vocab_set = set(symptoms_vocab)
        for item in llm_result["symptoms"]:
            token = str(item).strip().lower().replace(" ", "_")
            if token in vocab_set:
                normalized.append(token)
        llm_result["symptoms"] = list(dict.fromkeys(normalized))
        return llm_result

    vocab_hits = [symptom for symptom in symptoms_vocab if symptom.replace("_", " ") in text.lower()]
    return {"symptoms": vocab_hits[:10], "age": None, "gender": None}


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass

    if not isinstance(content, str):
        return {}
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def run_reasoning_step(
    input_text: str,
    base_prediction: str,
    extracted: dict,
    confidence: float,
    abha_records: list[dict],
) -> dict[str, Any]:
    if not _api_keys():
        return {
            "note": "Confidence below threshold; reasoning unavailable (OPENROUTER_API_KEY not configured).",
            "refined_disease": None,
            "llm_used": False,
        }

    messages = [
        {
            "role": "system",
            "content": (
                "You are the secondary diagnostic reasoning step. "
                "Return strict JSON with keys: refined_disease (string|null), note (string). "
                "If base prediction is inconsistent with gender context, propose safer alternative. "
                f"ABHA records: {json.dumps(abha_records)}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Input: {input_text}\nBase prediction: {base_prediction}\n"
                f"Extracted: {json.dumps(extracted)}\nConfidence: {confidence:.2f}"
            ),
        },
    ]
    try:
        content = _post_with_fallback(messages=messages, temperature=0.2)
    except LLMTimeoutError:
        raise
    except Exception:
        return {
            "note": "Secondary reasoning step failed due to upstream API error.",
            "refined_disease": None,
            "llm_used": False,
        }

    parsed = _parse_json_object(content)
    if parsed:
        return {
            "note": str(parsed.get("note", "")).strip() or "Secondary reasoning completed.",
            "refined_disease": parsed.get("refined_disease"),
            "llm_used": True,
        }
    return {
        "note": (content or "Secondary reasoning step failed due to upstream API error.").strip(),
        "refined_disease": None,
        "llm_used": bool(content),
    }
