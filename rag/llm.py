import os
import importlib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def complete(prompt):
    backend = os.environ.get("LLM_BACKEND", "gemini")
    try:
        mod = importlib.import_module(f"rag.backends.{backend}")
    except ModuleNotFoundError as e:
        raise RuntimeError(f"unknown LLM_BACKEND '{backend}': no rag/backends/{backend}.py") from e
    return mod.complete(prompt)
