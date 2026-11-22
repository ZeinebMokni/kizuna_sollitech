from .models import AgentFinding, DecisionRequest


def water_agent(request: DecisionRequest) -> AgentFinding:
    critical = [z for z in request.zones if z.moisture_percent < z.target_min_percent]
    if critical:
        names = ", ".join(z.zone_id for z in critical)
        return AgentFinding(
            agent_id="water-agriculture",
            focus="Eau et irrigation",
            status="critical",
            observation=f"{len(critical)} zone(s) sous le seuil: {names}.",
            recommendation="Proposer une irrigation ciblée uniquement après confirmation terrain.",
            confidence=92,
            sources=["soil telemetry", "crop thresholds"],
            checkpoints=["Confirmer le capteur sur place", "Vérifier débit et pression", "Mesurer l humidité après cycle"],
        )
    return AgentFinding(
        agent_id="water-agriculture", focus="Eau et irrigation", status="ok",
        observation="Les zones sont dans leurs seuils actuels.",
        recommendation="Éviter un cycle inutile et continuer la mesure.", confidence=88,
        sources=["soil telemetry", "crop thresholds"],
        checkpoints=["Comparer avec l historique sur 24 h"],
    )


def energy_agent(request: DecisionRequest) -> AgentFinding:
    surplus = max(0, request.energy.solar_kw - request.energy.pump_kw)
    if request.emergency_stop:
        status = "blocked"
        recommendation = "Ne commander aucun équipement pendant l arrêt d urgence."
    elif surplus > 0.5:
        status = "ok"
        recommendation = "Planifier les charges flexibles dans la fenêtre solaire."
    else:
        status = "warning"
        recommendation = "Attendre une meilleure production ou vérifier la batterie avant pompage."
    return AgentFinding(
        agent_id="energy-optimizer", focus="Énergie solaire", status=status,
        observation=f"Production {request.energy.solar_kw:.1f} kW, pompe {request.energy.pump_kw:.1f} kW, surplus {surplus:.1f} kW.",
        recommendation=recommendation, confidence=86,
        sources=["PV inverter", "battery BMS", "pump telemetry"],
        checkpoints=["Vérifier la puissance disponible", "Ne pas dépasser la réserve batterie"],
    )


def safety_agent(request: DecisionRequest) -> AgentFinding:
    if request.emergency_stop:
        return AgentFinding(
            agent_id="safety-guard", focus="Sécurité", status="blocked",
            observation="Arrêt d urgence actif.", recommendation="Bloquer toute commande terrain.", confidence=100,
            sources=["farm safety state"], checkpoints=["Validation humaine avant reprise"],
        )
    return AgentFinding(
        agent_id="safety-guard", focus="Sécurité", status="ok",
        observation="Aucun arrêt d urgence signalé.", recommendation="Autoriser uniquement les actions dans les limites définies.", confidence=99,
        sources=["farm safety state"], checkpoints=["Journaliser chaque commande"],
    )
