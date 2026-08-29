import asyncio
import os

from client.adapters.groq_adapter import GroqAdapter


def test_groq_adapter_missing_key_returns_error():
    os.environ.pop("GROQ_API_KEY", None)
    adapter = GroqAdapter(worker_id="w1", nickname="groq")

    result = asyncio.run(adapter.execute_task("task-1", "Return a simple answer.", "research", {}))

    assert result["success"] is False
    assert result["error"] == "Missing GROQ_API_KEY"


def test_groq_adapter_uses_env_model_override():
    os.environ["GROQ_API_KEY"] = "test-key"
    os.environ["GROQ_MODEL"] = "llama-3.1-8b-instant"

    adapter = GroqAdapter(worker_id="w1", nickname="groq")

    assert adapter.model == "llama-3.1-8b-instant"

    os.environ.pop("GROQ_MODEL", None)
    os.environ.pop("GROQ_API_KEY", None)
