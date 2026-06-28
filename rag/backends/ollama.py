import os
import requests

URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")


def complete(prompt):
    model = os.environ.get("LLM_MODEL", "qwen2.5-coder:7b")
    resp = requests.post(URL, json={"model": model, "prompt": prompt, "stream": False}, timeout=120)
    resp.raise_for_status()
    return resp.json()["response"]
