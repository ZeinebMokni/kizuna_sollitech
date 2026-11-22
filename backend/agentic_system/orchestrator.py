from datetime import datetime, timezone
from uuid import uuid4

from .agents import energy_agent, safety_agent, water_agent
from .models import DecisionRequest, DecisionResponse


class QatraOrchestrator:
    """Coordinates specialist agents and never hides their evidence."""

    def decide(self, request: DecisionRequest) -> DecisionResponse:
        findings = [safety_agent(request), water_agent(request), energy_agent(request)]
        blocked = any(f.status == "blocked" for f in findings)
        critical = any(f.status == "critical" for f in findings)
        if blocked:
            status = "blocked"
            recommendation = "Action bloquée par le garde-fou de sécurité."
        elif critical or request.human_validation:
            status = "human_review"
            recommendation = "Recommandation prête pour validation humaine."
        else:
            status = "proposed"
            recommendation = "Aucune action critique automatique nécessaire."
        solar_surplus = max(0, request.energy.solar_kw - request.energy.pump_kw)
        return DecisionResponse(
            decision_id=f"dec-{uuid4().hex[:12]}", farm_id=request.farm_id, status=status,
            recommendation=recommendation,
            expected_impact={"solar_surplus_kw": round(solar_surplus, 2), "critical_zones": sum(f.status == "critical" for f in findings), "action": "measure_before_generalize"},
            findings=findings, sources=request.sources,
            human_validation_required=status != "proposed",
            created_at=datetime.now(timezone.utc),
        )
