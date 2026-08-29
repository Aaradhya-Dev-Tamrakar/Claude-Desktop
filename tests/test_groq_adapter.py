import asyncio
import os

from client.adapters.groq_adapter import GroqAdapter


def test_groq_adapter_missing_key_returns_error():
    os.environ.pop("GROQ_API_KEY", None)
    adapter = GroqAdapter(worker_id="w1", nickname="groq")

    result = asyncio.run(adapter.execute_task("task-1", "Return a simple answer.", "research", {}))

    assert result["success"] is False
    assert result["error"] == "Missing GROQ_API_KEY"
