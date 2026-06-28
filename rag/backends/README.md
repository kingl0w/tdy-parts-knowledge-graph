# LLM backends

Each backend is one file exposing a single function:

    def complete(prompt: str) -> str

That is the entire contract. Any model that takes text and returns text fits.

Select a backend in `.env`:

    LLM_BACKEND=gemini
    LLM_MODEL=gemini-2.0-flash

To add a provider, copy `gemini.py`, swap in that provider's SDK call inside
`complete()`, and set `LLM_BACKEND` to the new filename (without `.py`).
Nothing else in the project changes.
