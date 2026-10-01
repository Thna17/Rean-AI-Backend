"""Grounded response builder for V3 pipeline.

Forces response content to align with RetrievalBundleV3 evidence.
This is a template-based implementation that can be swapped with LLM later.
"""

from __future__ import annotations

from typing import List

from api.models.v3_schemas import DiagnosisV3, RetrievalBundleV3
from api.services.kg_service_v3 import KnowledgeGraphServiceV3


class GroundedResponseV3:
    def __init__(self, kg: KnowledgeGraphServiceV3):
        self.kg = kg

    def build(self, text: str, diagnosis: DiagnosisV3, retrieval: RetrievalBundleV3) -> str:
        """Build a grounded tutor response using evidence + linked concepts."""
        concept_titles = self._resolve_titles(
            [c.id for c in retrieval.vector_hits][:2] + retrieval.kg_hits.seed_nodes
        )

        lines: List[str] = []
        if diagnosis.suspected_errors:
            err = diagnosis.suspected_errors[0]
            lines.append(f"Identified issue: {err.type} ({err.span}).")
        else:
            lines.append("I have analyzed your submission.")

        if concept_titles:
            lines.append("Related concepts: " + ", ".join(concept_titles) + ".")

        if retrieval.examples:
            ex = retrieval.examples[0]
            lines.append(f"Correct formulation: {ex.good}")
            lines.append(f"Incorrect formulation: {ex.bad}")
            if ex.why:
                lines.append(f"Explanation: {ex.why}")

        if diagnosis.intent == "practice":
            lines.append("Would you like to practice a similar problem? I can generate an exercise.")
        else:
            lines.append("Try re-evaluating the step based on the explanation above.")

        return "\n".join(lines)

    def _resolve_titles(self, concept_ids: List[str]) -> List[str]:
        concepts = self.kg.get_concepts()
        titles = []
        for cid in concept_ids:
            meta = concepts.get(cid)
            if meta and meta.get("title"):
                titles.append(meta["title"])
        return titles