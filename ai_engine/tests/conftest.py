import pytest


@pytest.fixture(autouse=True)
def _isolated_telemetry(tmp_path, monkeypatch):
    """Tests never write LLM telemetry into the real data directory."""
    monkeypatch.setenv("QATRA_TELEMETRY_PATH", str(tmp_path / "llm_events.jsonl"))
