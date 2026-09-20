"""Small client for OpenAI-compatible chat completion providers."""

import os
import requests

DEFAULT_BASE_URL = os.getenv(
    "AI_BASE_URL",
    os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1/chat/completions"),
)
DEFAULT_MODEL = os.getenv("AI_MODEL", os.getenv("NVIDIA_MODEL", "moonshotai/kimi-k3"))
REQUEST_TIMEOUT = float(os.getenv("NVIDIA_REQUEST_TIMEOUT", "180"))


class LLMError(Exception):
    pass


def call_llm(messages, api_key, model=None, temperature=0.4, max_tokens=800):
    if not api_key:
        raise LLMError("Missing AI API key. Set AI_API_KEY in api.env, or paste one in the top bar.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,  # this app reads one full response at a time, not a token stream
    }

    try:
        resp = requests.post(
            DEFAULT_BASE_URL,
            headers=headers,
            json=payload,
            timeout=(10, REQUEST_TIMEOUT),
        )
    except requests.RequestException as e:
        raise LLMError(
            f"AI request timed out or failed after {REQUEST_TIMEOUT:g}s. "
            f"Check AI_MODEL, AI_BASE_URL, and provider availability: {e}"
        ) from e

    if resp.status_code != 200:
        raise LLMError(f"API returned an error ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected response shape: {data}") from e
