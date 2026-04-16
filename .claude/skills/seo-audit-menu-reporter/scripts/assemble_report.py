#!/usr/bin/env python3
"""
assemble_report.py — Assemble un rapport Markdown depuis les findings JSON.

Agrège les findings des 6 spécialistes (+ comparator en mode comparaison),
applique la structure standardisée, et produit un Markdown prêt à livrer.

Usage :
    python3 assemble_report.py \
        --audit-dir audits/2026-04-16-site/ \
        --output audits/2026-04-16-site/reports/report-draft.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


SEVERITY_ORDER = ["bloquant", "critique", "important", "recommandation"]
SEVERITY_EMOJI = {
    "bloquant": "🚫",
    "critique": "🔴",
    "important": "⚠️",
    "recommandation": "💡",
}
SEVERITY_LABEL = {
    "bloquant": "BLOQUANT",
    "critique": "CRITIQUE",
    "important": "IMPORTANT",
    "recommandation": "RECOMMANDATION",
}

DIMENSIONS_ORDER = [
    ("semantic", "Structure HTML sémantique"),
    ("link-equity", "Maillage & équité de lien"),
    ("crawlability", "Crawlabilité & rendering"),
    ("accessibility", "Accessibilité & mobile-first"),
    ("performance", "Performance (CWV)"),
    ("architecture", "Architecture de l'information"),
]


def load_json_if_exists(path: Path) -> dict | None:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[assemble] WARNING: invalid JSON in {path}", file=sys.stderr)
            return None
    return None


def collect_issues(findings: dict, dimension_label: str) -> list[dict]:
    """Extrait les issues d'un JSON de findings avec label de dimension."""
    issues = findings.get("findings", []) or findings.get("issues", [])
    for issue in issues:
        issue.setdefault("_source_dimension", dimension_label)
    return issues


def group_by_severity(issues: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {s: [] for s in SEVERITY_ORDER}
    for issue in issues:
        sev = issue.get("severity", "recommandation").lower()
        if sev in grouped:
            grouped[sev].append(issue)
        else:
            grouped["recommandation"].append(issue)
    return grouped


def render_issue(issue: dict, index: int) -> str:
    """Rendu Markdown d'un finding."""
    code = issue.get("code", "NO_CODE")
    message = issue.get("message", "")
    detail = issue.get("detail", "")
    evidence = issue.get("evidence", "")
    url = issue.get("url", "")
    source = issue.get("_source_dimension", "")

    block = [f"### {index}. {message}\n"]
    block.append(f"**Code :** `{code}`  ")
    if source:
        block.append(f"**Domaine :** {source}  ")
    if url:
        block.append(f"**URL concernée :** `{url}`  ")
    block.append("")
    if detail:
        block.append(detail)
        block.append("")
    if evidence:
        if isinstance(evidence, list):
            block.append("**Preuves :**\n")
            for e in evidence[:10]:
                block.append(f"- `{e}`")
            if len(evidence) > 10:
                block.append(f"- _...et {len(evidence) - 10} autres_")
            block.append("")
        else:
            block.append("**Preuve :**\n")
            block.append(f"```\n{str(evidence)[:500]}\n```")
            block.append("")
    return "\n".join(block)


def render_dashboard(dimension_summaries: dict[str, dict]) -> str:
    """Rendu du tableau de bord des 6 dimensions."""
    lines = [
        "| Dimension | Verdict | Issues | Top priority |",
        "|-----------|---------|--------|--------------|",
    ]
    for key, label in DIMENSIONS_ORDER:
        summary = dimension_summaries.get(key)
        if summary:
            verdict = summary.get("verdict", "?")
            by_sev = summary.get("by_severity", {})
            total = sum(by_sev.values()) if by_sev else 0
            top_sev = next((s for s in SEVERITY_ORDER if by_sev.get(s, 0) > 0), None)
            top_label = f"{SEVERITY_EMOJI[top_sev]} {SEVERITY_LABEL[top_sev]}" if top_sev else "-"
            lines.append(f"| {label} | {verdict} | {total} | {top_label} |")
        else:
            lines.append(f"| {label} | _non analysé_ | - | - |")
    return "\n".join(lines)


def render_knowledge_section(title: str, items: list[str]) -> str:
    if not items:
        return f"### {title}\n\n_Aucun élément relevé._\n"
    lines = [f"### {title}\n"]
    for item in items:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble SEO audit report from findings")
    parser.add_argument("--audit-dir", required=True, help="Audit directory")
    parser.add_argument("--output", required=True, help="Output Markdown file")

    args = parser.parse_args()

    audit_dir = Path(args.audit_dir)
    findings_dir = audit_dir / "findings"

    if not findings_dir.exists():
        print(f"[assemble] ERROR: findings dir not found: {findings_dir}", file=sys.stderr)
        return 1

    # Charger intake
    intake_path = audit_dir / "intake.json"
    intake = load_json_if_exists(intake_path) or {}
    mode = intake.get("mode", "audit")
    site = intake.get("site", intake.get("url", "site inconnu"))

    # Charger chaque finding par dimension
    findings_per_dimension = {}
    all_issues = []
    dimension_summaries = {}
    all_i_know: list[str] = []
    all_i_think: list[str] = []
    all_i_cannot: list[str] = []

    for key, label in DIMENSIONS_ORDER:
        f = load_json_if_exists(findings_dir / f"{key}.json")
        if f:
            findings_per_dimension[key] = f
            issues = collect_issues(f, label)
            all_issues.extend(issues)
            dimension_summaries[key] = f.get("summary", {})
            all_i_know.extend(f.get("i_know", []))
            all_i_think.extend(f.get("i_think", []))
            all_i_cannot.extend(f.get("i_cannot_verify", []))

    # Comparator (mode comparaison)
    comparison = load_json_if_exists(findings_dir / "comparison.json")
    if comparison:
        all_issues.extend(collect_issues(comparison, "Comparaison avant/après"))

    # Groupement par sévérité
    grouped = group_by_severity(all_issues)

    # Compteurs
    total_by_sev = {s: len(grouped[s]) for s in SEVERITY_ORDER}
    total = sum(total_by_sev.values())

    # Verdict global
    if total_by_sev["bloquant"] > 0:
        global_verdict = "🚫 BLOQUANT — ne pas déployer en l'état"
    elif total_by_sev["critique"] > 2:
        global_verdict = "🔴 RISQUE ÉLEVÉ — corrections majeures requises"
    elif total_by_sev["critique"] > 0 or total_by_sev["important"] > 3:
        global_verdict = "⚠️ ATTENTION — ajustements nécessaires"
    else:
        global_verdict = "✅ OK — optimisations possibles"

    # Construction du Markdown
    lines = [
        f"# Audit SEO du menu de navigation — {site}",
        "",
        f"**Date :** {datetime.now().isoformat(timespec='seconds')}  ",
        f"**Mode :** {mode.upper()}  ",
        f"**Équipe d'audit :** 6 spécialistes + orchestration + review  ",
        "",
        "---",
        "",
        "## 1. Synthèse exécutive",
        "",
        f"**Verdict global :** {global_verdict}",
        "",
        f"- {total} findings consolidés au total",
        f"- 🚫 {total_by_sev['bloquant']} bloquants | 🔴 {total_by_sev['critique']} critiques | ⚠️ {total_by_sev['important']} importants | 💡 {total_by_sev['recommandation']} recommandations",
        "",
    ]

    # Top 3
    top_issues = []
    for sev in SEVERITY_ORDER:
        top_issues.extend(grouped[sev])
        if len(top_issues) >= 3:
            break

    if top_issues:
        lines.append("**Top 3 des points d'attention :**")
        lines.append("")
        for i, issue in enumerate(top_issues[:3], 1):
            emoji = SEVERITY_EMOJI.get(issue.get("severity", ""), "•")
            lines.append(f"{i}. {emoji} {issue.get('message', '')}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 2. Tableau de bord")
    lines.append("")
    lines.append(render_dashboard(dimension_summaries))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Problèmes identifiés")
    lines.append("")

    for sev in SEVERITY_ORDER:
        issues = grouped[sev]
        if not issues:
            continue
        emoji = SEVERITY_EMOJI[sev]
        label = SEVERITY_LABEL[sev]
        plural = "S" if len(issues) > 1 else ""
        lines.append(f"### {emoji} {label}{plural} ({len(issues)})")
        lines.append("")
        for i, issue in enumerate(issues, 1):
            lines.append(render_issue(issue, i))
        lines.append("---")
        lines.append("")

    # Mode comparaison : section dédiée
    if mode == "compare" and comparison:
        lines.append("## 4. Analyse différentielle (avant / après)")
        lines.append("")
        url_diff = comparison.get("url_diff", {})
        lines.append(f"- **URLs avant :** {url_diff.get('total_before', '-')}")
        lines.append(f"- **URLs après :** {url_diff.get('total_after', '-')}")
        lines.append(f"- **Net change :** {url_diff.get('net_change', '-')}")
        lines.append(f"- **URLs ajoutées :** {len(url_diff.get('added', []))}")
        lines.append(f"- **URLs supprimées :** {len(url_diff.get('removed', []))}")
        lines.append("")

        removed = url_diff.get("removed", [])
        if removed:
            lines.append("**URLs supprimées (risque d'orphelinage) :**")
            lines.append("")
            for url in removed[:20]:
                lines.append(f"- `{url}`")
            if len(removed) > 20:
                lines.append(f"- _...et {len(removed) - 20} autres_")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Méthodologie
    lines.append("## 5. Méthodologie — transparence sur l'analyse")
    lines.append("")
    lines.append("Pour préserver la crédibilité de cet audit, chaque constat est classé selon trois niveaux de confiance :")
    lines.append("")

    lines.append(render_knowledge_section("✅ JE SAIS (vérifié dans les données fournies)", all_i_know))
    lines.append(render_knowledge_section("🤔 JE PENSE (interprétation basée sur des sources documentées)", all_i_think))
    lines.append(render_knowledge_section("❓ JE NE PEUX PAS VÉRIFIER (nécessite accès live ou données complémentaires)", all_i_cannot))

    lines.append("---")
    lines.append("")
    lines.append("## 6. Prochaines étapes recommandées")
    lines.append("")

    if total_by_sev["bloquant"] > 0:
        lines.append("1. **URGENT** : corriger les bloquants avant toute mise en production / déploiement")
    if total_by_sev["critique"] > 0:
        lines.append("2. Planifier la correction des critiques dans le sprint suivant")
    if total_by_sev["important"] > 0:
        lines.append("3. Intégrer les importants dans la roadmap des 2-3 mois")
    lines.append("4. Mettre en place un monitoring post-déploiement (GSC, GA4) pour mesurer l'impact réel")
    lines.append("5. Refaire un audit comparatif 4-6 semaines après les corrections")
    lines.append("")

    # Annexes
    lines.append("---")
    lines.append("")
    lines.append("## Annexes")
    lines.append("")
    lines.append("### Findings bruts des spécialistes")
    lines.append("")
    for key, label in DIMENSIONS_ORDER:
        if key in findings_per_dimension:
            lines.append(f"- `audits/.../findings/{key}.json` — {label}")
    if comparison:
        lines.append("- `audits/.../findings/comparison.json` — Analyse différentielle")
    lines.append("")

    lines.append("### Sources primaires citées")
    lines.append("")
    lines.append("- Brevet Google US 7,716,225 — Reasonable Surfer Model")
    lines.append("- Brevet Google US 9,305,099 — Reasonable Surfer updated (2016)")
    lines.append("- Brevet Google US 8,898,296 — Boilerplate Detection")
    lines.append("- WCAG 2.1 (W3C)")
    lines.append("- WCAG 2.2 (W3C, octobre 2023)")
    lines.append("- Google Web.dev — Core Web Vitals")
    lines.append("- Matt Cutts (2009), John Mueller (2021) — First Link Priority")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Audit généré par seo-audit-for-claude-code — équipe orchestrator + 6 spécialistes + reporter + reviewer._")
    lines.append("")

    md = "\n".join(lines)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"[assemble] ✓ {out} ({len(md)} chars, {total} findings)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
