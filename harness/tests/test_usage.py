"""The context counter: token estimates and the usage endpoint."""

from __future__ import annotations

import httpx

from kicad_harness.agent import models as model_catalog
from kicad_harness.server import create_app, estimate_tokens
from kicad_harness.store.workspace import Workspace

from tests.test_phase import services  # noqa: F401  (pytest fixture)


def test_estimate_tokens_handles_models_and_dicts() -> None:
    class M:
        def model_dump(self, mode: str = "json") -> dict:
            return {"role": "user", "content": "x" * 400}

    assert estimate_tokens([M()]) and estimate_tokens([M()]) >= 100
    assert estimate_tokens([{"content": "y" * 400}]) >= 100
    assert estimate_tokens([]) is not None  # never raises, may be small


def test_budget_and_window_are_separate_numbers(monkeypatch) -> None:
    """max_tokens (output) and the context window are different limits."""
    class Cfg:
        bifrost_base_url = "https://gw.example/v1"
        bifrost_api_key = "k"

    monkeypatch.delenv("HARNESS_MAX_TOKENS", raising=False)
    monkeypatch.setattr(
        model_catalog, "_MODELS_CACHE",
        (__import__("time").monotonic(), Cfg.bifrost_base_url,
         [{"id": "zai/glm-5.3", "max_output_tokens": 128000, "context_length": 1000000}]),
    )
    assert model_catalog.budget_for("bifrost:zai/glm-5.3", Cfg()) == 128000
    assert model_catalog.context_window("bifrost:zai/glm-5.3", Cfg()) == 1000000


async def test_usage_endpoint_reports_limits_and_last_run(services) -> None:
    name = "usage-probe"
    Workspace.create_schematic(services.config, name, "nothing yet")
    app = create_app()
    app.state.services, app.state.metric_tasks = services, set()
    app.state.stop_flags = {}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/designs/{name}/usage")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model"]
    assert body["max_output_tokens"] > 0
    # A design with no runs yet still answers, with nothing to report.
    assert "last_run" in body
