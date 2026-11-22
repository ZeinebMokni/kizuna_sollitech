from pathlib import Path

from fastapi import APIRouter

from .models import DecisionRequest, DecisionResponse
from .orchestrator import QatraOrchestrator

router = APIRouter(prefix="/api/agentic", tags=["Multi-agent QATRA"])
orchestrator = QatraOrchestrator()
ENGINE_ROOT = Path(__file__).resolve().parent / "ai_engine"


@router.get("/agents")
async def list_agents():
    return {
        "agents": [
            {"id": "water-agriculture", "focus": "Eau et irrigation"},
            {"id": "energy-optimizer", "focus": "Énergie solaire"},
            {"id": "safety-guard", "focus": "Sécurité et arrêt d urgence"},
            {"id": "orchestrator", "focus": "Coordination et checkpoints"},
        ],
        "policy": "Les décisions critiques nécessitent une validation humaine.",
    }


@router.post("/decisions", response_model=DecisionResponse)
async def create_decision(request: DecisionRequest):
    return orchestrator.decide(request)


@router.get("/health")
async def agentic_health():
    return {"status": "ready", "mode": "deterministic-scaffold", "human_validation": True}


@router.get("/engine")
async def engine_status():
    """Expose the imported AI engine without importing its optional heavy dependencies."""
    package_root = ENGINE_ROOT / "qatra_ai"
    return {
        "status": "available" if package_root.is_dir() else "missing",
        "source_branch": "AIengine",
        "path": "backend/agentic_system/ai_engine",
        "package": "qatra_ai",
        "capabilities": [
            "water-balance",
            "crop-suitability",
            "energy-optimization",
            "market-scenarios",
            "climate-and-anomalies",
            "assistant-and-strategy",
        ],
        "service_entrypoint": "qatra_ai.service.app:app",
        "integration": "The QATRA frontend uses /api/agentic/*; engine calls can be routed through an adapter.",
    }
