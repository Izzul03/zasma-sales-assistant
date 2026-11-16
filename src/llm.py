"""Optional LLM reader (Gemini or OpenAI through the OpenAI-compatible API).

The app works fully without a key. Keys come from Streamlit Secrets or .env only.
"""
from __future__ import annotations

import json
import os
from typing import Dict, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

BASE_URLS = {"gemini": "https://generativelanguage.googleapis.com/v1beta/openai/", "openai": None}
KEY_NAMES = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}
DEFAULT_MODELS = {"gemini": "gemini-2.5-flash", "openai": "gpt-4o-mini"}


def _setting(name: str) -> Optional[str]:
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name) or None


class LLM:
    def __init__(self, _client=None):
        self.provider = (_setting("LLM_PROVIDER") or "gemini").lower()
        if self.provider not in BASE_URLS:
            self.provider = "gemini"
        self.model = _setting("LLM_MODEL") or DEFAULT_MODELS[self.provider]
        self._key = _setting(KEY_NAMES[self.provider])
        self._client = _client

    @property
    def enabled(self) -> bool:
        return bool(self._key) or self._client is not None

    def json_completion(self, system: str, user: str, purpose: str = "") -> Dict:
        if self._client is None:
            if not self._key:
                raise RuntimeError("Kunci API belum ditetapkan.")
            from openai import OpenAI

            self._client = OpenAI(api_key=self._key, base_url=BASE_URLS[self.provider], timeout=45, max_retries=2)
        resp = self._client.chat.completions.create(
            model=self.model, temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        text = (resp.choices[0].message.content or "").strip().strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        return json.loads(text[text.find("{"): text.rfind("}") + 1])
