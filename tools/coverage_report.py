#!/usr/bin/env python3
"""
coverage_report.py — Calcule la couverture d'un audit par rapport à la checklist v0.3.

Lit les findings JSON d'un dossier d'audit, croise avec les 67 items de la checklist,
produit un rapport de couverture (combien d'items testés, lesquels manquent, pourquoi).

Usage :
    python3 tools/coverage_report.py --audit-dir audits/YYYYMMDD-site/ --output coverage.json

Le JSON de sortie est consommé par le reporter pour injecter la section Couverture dans le rapport.

Codes de sortie :
    0 : succès
    1 : dossier introuvable
    3 : erreur inattendue
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# Les 67 items de la checklist v0.3, avec leur ID et le script qui les couvre
CHECKLIST_V03: list[dict] = [
    # Partie 1 — Crawlabilité
    {"id": "1.1.1", "name": "Liens nav dans source pré-JS", "script": "diff_source_vs_rendered", "type": "STATIC+DYNAMIC"},
    {"id": "1.1.2", "name": "Détection framework", "script": "parse_nav", "type": "STATIC"},
    {"id": "1.1.3", "name": "User-Agent Googlebot diff", "script": "fetch_googlebot", "type": "DYNAMIC"},
    {"id": "1.2.1", "name": "Click depth pages stratégiques", "script": "parse_nav", "type": "STATIC"},
    {"id": "1.2.2", "name": "Profondeur menu", "script": "parse_nav", "type": "STATIC"},
    {"id": "1.3.1", "name": "Liens injectés après interaction", "script": "burger_capture", "type": "DYNAMIC"},
    {"id": "1.3.2", "name": "Hover sans focus equivalent", "script": "css_analyzer", "type": "STATIC+DYNAMIC"},
    {"id": "1.3.3", "name": "Off-canvas drawer SSR", "script": "diff_source_vs_rendered", "type": "DYNAMIC"},
    {"id": "1.4.1", "name": "URLs menu → sitemap", "script": "sitemap_alignment", "type": "STATIC"},
    {"id": "1.4.2", "name": "Menu → robots.txt", "script": "sitemap_alignment", "type": "STATIC"},
    {"id": "1.4.3", "name": "Meta robots noindex menu URLs", "script": "url_status_checker", "type": "STATIC"},
    {"id": "1.5.1", "name": "Parité menu mobile/desktop", "script": "viewport_content_parity", "type": "DYNAMIC"},
    {"id": "1.5.2", "name": "Viewport meta tag", "script": "parse_nav", "type": "STATIC"},
    {"id": "1.5.3", "name": "Media queries hostiles", "script": "css_analyzer", "type": "STATIC"},
    # Partie 2 — Link equity
    {"id": "2.1.1", "name": "Position nav dans DOM source", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.1.2", "name": "Cohérence topicale", "script": "llm_reasoning", "type": "LLM"},
    {"id": "2.2.1", "name": "Nombre total liens nav", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.2.2", "name": "Ratio nav/contenu", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.2.3", "name": "Duplication contenu mega menu", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.3.1", "name": "Liens multiples même URL", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.3.2", "name": "Collision logo + premier item", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.4.1", "name": "Ancres génériques", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.4.2", "name": "Ancres vides", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.4.3", "name": "Diversité ancres par URL", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.4.4", "name": "Cohérence ancres zones", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.5.1", "name": "URLs footer-only", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.5.2", "name": "Liens externes footer nofollow", "script": "parse_nav", "type": "STATIC"},
    {"id": "2.6.1", "name": "Hiérarchie thématique", "script": "llm_reasoning", "type": "LLM"},
    # Partie 3 — Accessibilité
    {"id": "3.1.1", "name": "Balise <nav>", "script": "accessibility_checks", "type": "STATIC"},
    {"id": "3.1.2", "name": "Anti-pattern role=menu", "script": "accessibility_checks", "type": "STATIC"},
    {"id": "3.1.3", "name": "Labels nav multiples", "script": "accessibility_checks", "type": "STATIC"},
    {"id": "3.1.4", "name": "aria-current=page", "script": "accessibility_checks", "type": "STATIC"},
    {"id": "3.2.1", "name": "Focus Appearance WCAG 2.2", "script": "accessibility_dynamic", "type": "DYNAMIC"},
    {"id": "3.2.2", "name": "Hover on Focus WCAG 2.2", "script": "css_analyzer", "type": "STATIC+DYNAMIC"},
    {"id": "3.2.3", "name": "Target Size 24x24", "script": "accessibility_dynamic", "type": "DYNAMIC"},
    {"id": "3.2.4", "name": "Focus Visible", "script": "accessibility_checks", "type": "STATIC"},
    {"id": "3.3.1", "name": "Skip link", "script": "accessibility_dynamic", "type": "STATIC"},
    {"id": "3.4.1", "name": "Escape ferme sous-menu", "script": "accessibility_dynamic", "type": "DYNAMIC"},
    {"id": "3.4.2", "name": "Trigger = button", "script": "accessibility_checks", "type": "STATIC"},
    {"id": "3.4.3", "name": "Focus management", "script": "accessibility_dynamic", "type": "DYNAMIC"},
    # Partie 4 — Performance
    {"id": "4.1.1", "name": "INP 200ms", "script": "performance_checks", "type": "DYNAMIC"},
    {"id": "4.1.2", "name": "Event handlers lourds", "script": "llm_reasoning", "type": "LLM"},
    {"id": "4.2.1", "name": "Sticky header CLS", "script": "performance_checks", "type": "DYNAMIC"},
    {"id": "4.2.2", "name": "Hauteur header hydratation", "script": "performance_checks", "type": "DYNAMIC"},
    {"id": "4.2.3", "name": "Occupation viewport mobile", "script": "performance_checks", "type": "DYNAMIC"},
    {"id": "4.3.1", "name": "Menu comme LCP", "script": "performance_checks", "type": "DYNAMIC"},
    {"id": "4.3.2", "name": "Scripts bloquants avant menu", "script": "parse_nav", "type": "STATIC"},
    # Partie 5 — Breadcrumbs
    {"id": "5.1.1", "name": "Pattern breadcrumb ARIA", "script": "breadcrumb_checks", "type": "STATIC"},
    {"id": "5.2.1", "name": "JSON-LD BreadcrumbList", "script": "breadcrumb_checks", "type": "STATIC"},
    {"id": "5.2.2", "name": "Alignement HTML → JSON-LD", "script": "breadcrumb_checks", "type": "STATIC"},
    {"id": "5.2.3", "name": "URLs absolues dans item", "script": "breadcrumb_checks", "type": "STATIC"},
    # Partie 6 — Facettes
    {"id": "6.1.1", "name": "Facettes dans menu", "script": "parse_nav", "type": "STATIC"},
    {"id": "6.1.2", "name": "rel=nofollow sur facettes", "script": "parse_nav", "type": "STATIC"},
    # Partie 7 — i18n
    {"id": "7.1.1", "name": "Sélecteur menu → hreflang", "script": "i18n_checks", "type": "STATIC"},
    {"id": "7.1.2", "name": "Self-referencing hreflang", "script": "i18n_checks", "type": "STATIC"},
    {"id": "7.1.3", "name": "x-default", "script": "i18n_checks", "type": "STATIC"},
    # Partie 8 — Redirections
    {"id": "8.1.1", "name": "Statut HTTP URLs supprimées", "script": "url_status_checker", "type": "STATIC"},
    {"id": "8.1.2", "name": "Changement ancre même URL", "script": "compare_menus", "type": "STATIC"},
    {"id": "8.2.1", "name": "URLs nouvelles", "script": "compare_menus", "type": "STATIC+LLM"},
    # Partie 9 — Consistency
    {"id": "9.2.1", "name": "Liens brisés 4xx/5xx", "script": "url_status_checker", "type": "STATIC"},
    {"id": "9.2.2", "name": "Redirects domaines externes", "script": "url_status_checker", "type": "STATIC"},
    {"id": "9.3.1", "name": "Parité multi-templates", "script": "orchestrator_multi_fetch", "type": "DYNAMIC"},
    # Partie 10 — Schema
    {"id": "10.1", "name": "SiteNavigationElement schema", "script": "parse_nav", "type": "STATIC"},
    # Partie 11 — UX
    {"id": "11.1.1", "name": "Nombre items top-level", "script": "parse_nav", "type": "STATIC"},
    {"id": "11.1.2", "name": "Labels jargon", "script": "llm_reasoning", "type": "LLM"},
    {"id": "11.2.1", "name": "Search dans menu", "script": "parse_nav", "type": "STATIC"},
]


def scan_findings(audit_dir: Path) -> set[str]:
    """Lit tous les findings JSON et retourne les checklist_id couverts."""
    covered_ids: set[str] = set()
    findings_dir = audit_dir / "findings"
    if not findings_dir.exists():
        return covered_ids

    for f in findings_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        # Format 1 : liste de findings avec checklist_id
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "checklist_id" in item:
                    covered_ids.add(item["checklist_id"])

        # Format 2 : dict avec "tests" (accessibility_checks, breadcrumb_checks, etc.)
        if isinstance(data, dict):
            for test in data.get("tests", []):
                if isinstance(test, dict) and "checklist_id" in test:
                    # Un checklist_id peut contenir plusieurs IDs séparés par " + "
                    for cid in test["checklist_id"].split(" + "):
                        covered_ids.add(cid.strip())

            # Format 3 : dict avec "findings" array
            for finding in data.get("findings", []):
                if isinstance(finding, dict) and "checklist_id" in finding:
                    covered_ids.add(finding["checklist_id"])

            # Format 4 : dict avec "issues" array (sitemap_alignment)
            for issue in data.get("issues", []):
                if isinstance(issue, dict) and "checklist_id" in issue:
                    covered_ids.add(issue["checklist_id"])

    return covered_ids


def check_script_output_exists(audit_dir: Path, script_name: str) -> bool:
    """Vérifie si un script a produit un output dans le dossier d'audit."""
    findings_dir = audit_dir / "findings"
    pages_dir = audit_dir / "pages"

    # Heuristiques de présence par script
    patterns = {
        "parse_nav": findings_dir / "*.json",
        "diff_source_vs_rendered": findings_dir / "crawlability*.json",
        "url_status_checker": findings_dir / "*status*.json",
        "sitemap_alignment": findings_dir / "*sitemap*.json",
        "accessibility_checks": findings_dir / "*accessibility*.json",
        "accessibility_dynamic": findings_dir / "*accessibility*.json",
        "performance_checks": findings_dir / "*performance*.json",
        "breadcrumb_checks": findings_dir / "*breadcrumb*.json",
        "i18n_checks": findings_dir / "*i18n*.json",
        "css_analyzer": findings_dir / "*css*.json",
        "fetch_googlebot": findings_dir / "*googlebot*.json",
        "viewport_content_parity": findings_dir / "*viewport*.json",
        "burger_capture": pages_dir / "*burger*.json",
        "compare_menus": findings_dir / "*compar*.json",
    }

    pattern = patterns.get(script_name)
    if pattern:
        return len(list(pattern.parent.glob(pattern.name))) > 0
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Calcule la couverture d'un audit vs checklist v0.3")
    parser.add_argument("--audit-dir", required=True, help="Dossier de l'audit (audits/YYYYMMDD-site/)")
    parser.add_argument("--output", required=True, help="Fichier JSON de sortie")

    args = parser.parse_args()

    audit_dir = Path(args.audit_dir)
    if not audit_dir.exists():
        print(f"[coverage_report] ✗ Dossier introuvable : {args.audit_dir}", file=sys.stderr)
        return 1

    print(f"[coverage_report] Analyse de couverture pour : {audit_dir}", file=sys.stderr)

    # Scanner les findings
    covered_ids = scan_findings(audit_dir)

    # Calculer la couverture
    items = []
    for check in CHECKLIST_V03:
        cid = check["id"]
        has_finding = cid in covered_ids
        has_script_output = check_script_output_exists(audit_dir, check["script"])

        if has_finding:
            status = "tested"
        elif has_script_output:
            status = "script_ran_no_finding"
        elif check["type"] == "LLM":
            status = "llm_judgment"
        else:
            status = "not_tested"

        items.append({
            "id": cid,
            "name": check["name"],
            "script": check["script"],
            "type": check["type"],
            "status": status,
        })

    tested = sum(1 for i in items if i["status"] in ("tested", "script_ran_no_finding", "llm_judgment"))
    not_tested = sum(1 for i in items if i["status"] == "not_tested")

    result = {
        "audit_dir": str(audit_dir),
        "checklist_version": "v0.3",
        "total_items": len(CHECKLIST_V03),
        "tested": tested,
        "not_tested": not_tested,
        "coverage_percent": round(tested / len(CHECKLIST_V03) * 100),
        "items": items,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"[coverage_report] ✓ Couverture : {tested}/{len(CHECKLIST_V03)} items "
        f"({result['coverage_percent']}%). {not_tested} non testés.",
        file=sys.stderr,
    )
    print(json.dumps({
        "coverage_percent": result["coverage_percent"],
        "tested": tested,
        "not_tested": not_tested,
        "output_file": args.output,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[coverage_report] ✗ Erreur inattendue : {e}", file=sys.stderr)
        sys.exit(3)
