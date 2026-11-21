"""Read-only tools the assistant may call. They return engine outputs; they never compute new
recommendations, never write state, and never actuate hardware.

Every result is wrapped as {"result_id": "r<n>", "tool": ..., "data": ..., "notes": [...]}
so the answer can cite it and the grounding verifier can check numbers against it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from qatra_ai.agronomy.crops import get_crop, load_crop_profiles
from qatra_ai.contracts import EngineEnvelope
from qatra_ai.optimization.allocation import AllocationComparison
from qatra_ai.orchestrator.decision import FarmDecision
from qatra_ai.predictive.anomaly import AnomalyEvent
from qatra_ai.suitability.engine import CropSuitability


class ToolError(ValueError):
    """Invalid tool input: returned to the model as an is_error tool_result."""


@dataclass
class AssistantContext:
    """Engine outputs the assistant is allowed to read (any of them may be absent)."""

    decision: EngineEnvelope[FarmDecision] | None = None
    suitability: list[CropSuitability] | None = None
    anomalies: list[AnomalyEvent] | None = None
    allocation: EngineEnvelope[AllocationComparison] | None = None


def _schema(props: dict[str, Any] | None = None, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": props or {},
        "required": required or [],
        "additionalProperties": False,
    }


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_decisions",
        "description": "List the farm's ranked decision packages (rank, tier, action, target, "
        "amount, confidence). Use this first for any question about what to do or why.",
        "input_schema": _schema(),
    },
    {
        "name": "get_decision",
        "description": "Full detail of one decision package: reasons, measurements with "
        "provenance, binding constraints, expected impact, alternatives, data limitations, "
        "and the priority trace explaining its rank.",
        "input_schema": _schema({"package_id": {"type": "string"}}, ["package_id"]),
    },
    {
        "name": "compare_priority",
        "description": "Explain why one decision package ranks above another, using the "
        "engine's lexicographic rule (tier, then time to stress, then avoided stress per m3).",
        "input_schema": _schema(
            {"package_a": {"type": "string"}, "package_b": {"type": "string"}},
            ["package_a", "package_b"],
        ),
    },
    {
        "name": "get_crop_profile",
        "description": "Agronomic parameters of a crop with their citations and review status. "
        "Codes: tomato, potato, durum_wheat, olive, citrus, date_palm.",
        "input_schema": _schema({"crop_code": {"type": "string"}}, ["crop_code"]),
    },
    {
        "name": "get_suitability",
        "description": "Crop suitability assessments (FAO limiting-factor classes S1/S2/S3/N/U, "
        "factor values, provisional warnings, trade-off indicators). Optional crop_code filter; "
        "empty string returns all crops.",
        "input_schema": _schema({"crop_code": {"type": "string"}}, ["crop_code"]),
    },
    {
        "name": "get_anomalies",
        "description": "Detected water anomalies with possible causes, evidence, estimated "
        "volume, severity, confidence and recommended checks.",
        "input_schema": _schema(),
    },
    {
        "name": "get_allocation_comparison",
        "description": "Comparison of water allocation strategies between farms (allocations, "
        "satisfaction, loss, fairness metrics, marginal value of water) and its disclaimer.",
        "input_schema": _schema(),
    },
]


@dataclass
class ToolRegistry:
    ctx: AssistantContext
    results: dict[str, dict] = field(default_factory=dict)

    def _wrap(self, tool: str, data: Any, notes: list[str] | None = None) -> dict:
        rid = f"r{len(self.results) + 1}"
        out = {"result_id": rid, "tool": tool, "data": data, "notes": notes or []}
        self.results[rid] = out
        return out

    def _decision(self) -> FarmDecision:
        if self.ctx.decision is None or self.ctx.decision.payload is None:
            raise ToolError("no decision packages are available for this farm right now")
        return self.ctx.decision.payload

    def _package(self, pid: str):
        for p in self._decision().packages:
            if p.package_id == pid:
                return p
        ids = [p.package_id for p in self._decision().packages]
        raise ToolError(f"unknown package_id {pid!r}; valid ids: {ids}")

    def call(self, name: str, args: dict[str, Any]) -> str:
        """Execute a tool; returns the JSON string sent back as the tool_result content."""
        handler = getattr(self, f"_t_{name}", None)
        if handler is None:
            raise ToolError(f"unknown tool {name!r}")
        return json.dumps(handler(**args), ensure_ascii=False, default=str)

    # --- tool implementations -----------------------------------------------------------

    def _t_list_decisions(self) -> dict:
        d = self._decision()
        env = self.ctx.decision
        rows = [
            {
                "package_id": p.package_id,
                "rank": p.rank,
                "tier": p.tier,
                "tier_label": p.tier_label,
                "action": p.action,
                "target": p.target,
                "amount": p.amount.model_dump() if p.amount else None,
                "confidence": p.confidence.value,
                "requires_human_approval": p.requires_human_approval,
            }
            for p in d.packages
        ]
        return self._wrap(
            "list_decisions",
            {
                "farm_id": d.farm_id,
                "as_of": str(d.as_of),
                "packages": rows,
                "overall_confidence": env.confidence.value if env else None,
                "model_validation_status": env.model.validation_status.value if env else None,
            },
            notes=list(env.limitations) if env else [],
        )

    def _t_get_decision(self, package_id: str) -> dict:
        p = self._package(package_id)
        return self._wrap(
            "get_decision",
            p.model_dump(mode="json"),
            notes=["proposal for human review; nothing is executed automatically"],
        )

    def _t_compare_priority(self, package_a: str, package_b: str) -> dict:
        a, b = self._package(package_a), self._package(package_b)
        hi, lo = (a, b) if a.rank < b.rank else (b, a)
        if hi.tier != lo.tier:
            rule = (
                f"different tiers: tier {hi.tier} ({hi.tier_label}) outranks tier {lo.tier} "
                f"({lo.tier_label})"
            )
        else:
            rule = "same tier: ordered by time to stress, then avoided stress per m3"
        return self._wrap(
            "compare_priority",
            {
                "higher": {
                    "package_id": hi.package_id,
                    "rank": hi.rank,
                    "tier": hi.tier,
                    "target": hi.target,
                    "trace": hi.priority_trace,
                },
                "lower": {
                    "package_id": lo.package_id,
                    "rank": lo.rank,
                    "tier": lo.tier,
                    "target": lo.target,
                    "trace": lo.priority_trace,
                },
                "deciding_rule": rule,
            },
        )

    def _t_get_crop_profile(self, crop_code: str) -> dict:
        try:
            c = get_crop(crop_code)
        except KeyError as exc:
            raise ToolError(
                f"unknown crop {crop_code!r}; known: {sorted(load_crop_profiles())}"
            ) from exc
        return self._wrap(
            "get_crop_profile",
            c.model_dump(mode="json"),
            notes=[f"review_status: {c.review_status}"],
        )

    def _t_get_suitability(self, crop_code: str) -> dict:
        if not self.ctx.suitability:
            raise ToolError("no suitability assessment is available")
        rows = [r for r in self.ctx.suitability if not crop_code or r.crop == crop_code]
        if not rows:
            raise ToolError(f"no assessment for {crop_code!r}")
        return self._wrap(
            "get_suitability",
            [r.model_dump(mode="json") for r in rows],
            notes=[
                "classes are FAO limiting-factor classes; market is not "
                "integrated; provisional factors rest on unverified thresholds"
            ],
        )

    def _t_get_anomalies(self) -> dict:
        if self.ctx.anomalies is None:
            raise ToolError("no hydraulic data was analysed")
        return self._wrap(
            "get_anomalies",
            [e.model_dump(mode="json") for e in self.ctx.anomalies],
            notes=["possible causes are hypotheses; nothing is concluded about people"],
        )

    def _t_get_allocation_comparison(self) -> dict:
        if self.ctx.allocation is None or self.ctx.allocation.payload is None:
            raise ToolError("no allocation comparison is available")
        p = self.ctx.allocation.payload
        return self._wrap(
            "get_allocation_comparison", p.model_dump(mode="json"), notes=[p.disclaimer]
        )
