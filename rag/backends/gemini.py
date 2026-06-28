import os
from google import genai

_client = None


def _get_client():
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set (put it in .env)")
        _client = genai.Client(api_key=key)
    return _client


def complete(prompt):
    model = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
    resp = _get_client().models.generate_content(model=model, contents=prompt)
    return resp.text
