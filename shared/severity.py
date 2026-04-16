"""
severity.py — Types partagés pour les verdicts et sévérités.

Les 4 niveaux de sévérité + la structure Issue utilisée par tous les scripts
de l'audit. Utiliser ces types plutôt que des strings nues partout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    """Les 4 niveaux de sévérité. Chaînes pour être directement JSON-sérialisables."""

    BLOCKING = "bloquant"
    CRITICAL = "critique"
    IMPORTANT = "important"
    RECOMMENDATION = "recommandation"

    @property
    def emoji(self) -> str:
        return {
            Severity.BLOCKING: "🚫",
            Severity.CRITICAL: "🔴",
            Severity.IMPORTANT: "⚠️",
            Severity.RECOMMENDATION: "💡",
        }[self]

    @property
    def label(self) -> str:
        return {
            Severity.BLOCKING: "BLOQUANT",
            Severity.CRITICAL: "CRITIQUE",
            Severity.IMPORTANT: "IMPORTANT",
            Severity.RECOMMENDATION: "RECOMMANDATION",
        }[self]

    @property
    def rank(self) -> int:
        """Pour trier : plus petit = plus grave."""
        return {
            Severity.BLOCKING: 0,
            Severity.CRITICAL: 1,
            Severity.IMPORTANT: 2,
            Severity.RECOMMENDATION: 3,
        }[self]


class Verdict(str, Enum):
    """Verdict global d'un audit ou d'une dimension."""

    OK = "OK"
    ATTENTION = "ATTENTION"
    HIGH_RISK = "RISQUE_ELEVE"
    BLOCKING = "BLOQUANT"


@dataclass
class Issue:
    """Structure commune d'un finding, utilisable par tous les agents."""

    severity: Severity
    dimension: str
    code: str
    message: str
    detail: str = ""
    url: str = ""
    evidence: str | list[str] = ""
    pages_concerned: list[str] = field(default_factory=list)
    source_agent: str = ""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "dimension": self.dimension,
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "url": self.url,
            "evidence": self.evidence,
            "pages_concerned": self.pages_concerned,
            "source_agent": self.source_agent,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Issue:
        sev_str = d.get("severity", "recommandation")
        try:
            sev = Severity(sev_str)
        except ValueError:
            sev = Severity.RECOMMENDATION
        return cls(
            severity=sev,
            dimension=d.get("dimension", ""),
            code=d.get("code", ""),
            message=d.get("message", ""),
            detail=d.get("detail", ""),
            url=d.get("url", ""),
            evidence=d.get("evidence", ""),
            pages_concerned=d.get("pages_concerned", []),
            source_agent=d.get("source_agent", ""),
        )


def verdict_from_issues(issues: list[Issue]) -> Verdict:
    """Calcule le verdict global à partir d'une liste d'issues."""
    if any(i.severity == Severity.BLOCKING for i in issues):
        return Verdict.BLOCKING
    critical_count = sum(1 for i in issues if i.severity == Severity.CRITICAL)
    important_count = sum(1 for i in issues if i.severity == Severity.IMPORTANT)
    if critical_count > 2:
        return Verdict.HIGH_RISK
    if critical_count > 0 or important_count > 3:
        return Verdict.ATTENTION
    return Verdict.OK
