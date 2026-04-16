#!/usr/bin/env python3
"""
compare_menus.py — Comparaison avant/après de deux parsings de menu.

Lit deux fichiers JSON produits par seo-audit-menu-parser (un AVANT, un APRÈS)
et produit un diff structuré des changements : URLs ajoutées/supprimées,
ancres modifiées, changements de profondeur, régressions sémantiques.

Usage :
    python3 compare_menus.py \
        --before parsed-before.json \
        --after parsed-after.json \
        --output comparison.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def load_parsed(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_url_to_anchor(parsed: dict) -> dict[str, list[str]]:
    """Retourne {url: [liste des ancres trouvées]} pour cet audit."""
    mapping: dict[str, list[str]] = {}
    for nav in parsed.get("navs", []):
        for link in nav.get("links", []):
            url = link.get("href", "")
            text = link.get("text", "").strip()
            if url and url != "#":
                mapping.setdefault(url, []).append(text)
    return mapping


def extract_url_to_depth(parsed: dict) -> dict[str, int]:
    """Retourne {url: profondeur minimale} pour cet audit."""
    mapping: dict[str, int] = {}
    for nav in parsed.get("navs", []):
        for link in nav.get("links", []):
            url = link.get("href", "")
            depth = link.get("depth", 0)
            if url and url != "#":
                if url not in mapping or depth < mapping[url]:
                    mapping[url] = depth
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare before/after menu parsings")
    parser.add_argument("--before", required=True, help="Path to before parsed JSON")
    parser.add_argument("--after", required=True, help="Path to after parsed JSON")
    parser.add_argument("--before-label", default="Menu avant", help="Label for before version")
    parser.add_argument("--after-label", default="Menu après", help="Label for after version")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()

    before_path = Path(args.before)
    after_path = Path(args.after)

    if not before_path.exists():
        print(f"[compare] ERROR: before file not found: {before_path}", file=sys.stderr)
        return 1
    if not after_path.exists():
        print(f"[compare] ERROR: after file not found: {after_path}", file=sys.stderr)
        return 1

    before = load_parsed(before_path)
    after = load_parsed(after_path)

    # URLs
    before_urls_map = extract_url_to_anchor(before)
    after_urls_map = extract_url_to_anchor(after)
    before_urls = set(before_urls_map.keys())
    after_urls = set(after_urls_map.keys())

    added = after_urls - before_urls
    removed = before_urls - after_urls
    kept = before_urls & after_urls

    # Ancres modifiées (pour URLs présentes dans les deux)
    anchor_changes = []
    for url in sorted(kept):
        before_anchors = set(before_urls_map.get(url, []))
        after_anchors = set(after_urls_map.get(url, []))
        if before_anchors != after_anchors:
            anchor_changes.append({
                "url": url,
                "before": sorted(list(before_anchors)),
                "after": sorted(list(after_anchors)),
            })

    # Profondeur
    before_depth = extract_url_to_depth(before)
    after_depth = extract_url_to_depth(after)
    depth_changes = []
    for url in sorted(kept):
        b = before_depth.get(url, 0)
        a = after_depth.get(url, 0)
        if b != a:
            depth_changes.append({
                "url": url,
                "before_depth": b,
                "after_depth": a,
                "delta": a - b,
            })

    # Régressions sémantiques
    semantic_regressions = []

    before_semantic = before.get("semantic_structure", {})
    after_semantic = after.get("semantic_structure", {})

    for key in ["has_header", "has_nav", "has_main", "has_footer"]:
        if before_semantic.get(key) and not after_semantic.get(key):
            semantic_regressions.append({
                "type": f"{key}_removed",
                "detail": f"Élément <{key.replace('has_', '')}> présent avant, absent après",
            })

    # aria-label
    before_aria = [(n.get("nav_index"), n.get("aria_label")) for n in before.get("navs", [])]
    after_aria = [(n.get("nav_index"), n.get("aria_label")) for n in after.get("navs", [])]
    before_with_label = sum(1 for _, l in before_aria if l)
    after_with_label = sum(1 for _, l in after_aria if l)

    if after_with_label < before_with_label:
        semantic_regressions.append({
            "type": "aria_labels_reduced",
            "detail": f"Nombre de <nav> avec aria-label : {before_with_label} → {after_with_label}",
        })

    # Métriques globales
    before_metrics = before.get("metrics", {})
    after_metrics = after.get("metrics", {})

    before_total = before_metrics.get("total_nav_links", 0)
    after_total = after_metrics.get("total_nav_links", 0)

    # Issues consolidées
    issues = []

    if removed:
        issues.append({
            "severity": "bloquant" if len(removed) > 5 else "critique",
            "dimension": "comparison",
            "code": "URLS_REMOVED_FROM_NAV",
            "message": f"{len(removed)} URL(s) supprimée(s) du menu",
            "detail": (
                "Ces pages ne reçoivent plus d'équité depuis la homepage. Risque d'orphelinage. "
                "Vérifier que chacune est soit redirigée (301 vers page pertinente), "
                "soit encore liée depuis d'autres pages du site."
            ),
            "evidence": sorted(list(removed))[:20],
        })

    if added:
        issues.append({
            "severity": "recommandation",
            "dimension": "comparison",
            "code": "URLS_ADDED_TO_NAV",
            "message": f"{len(added)} nouvelle(s) URL(s) ajoutée(s) au menu",
            "detail": (
                "Vérifier que ces URLs pointent vers des pages existantes (HTTP 200). "
                "Vérifier que le contenu est publié et complet."
            ),
            "evidence": sorted(list(added))[:20],
        })

    if anchor_changes:
        issues.append({
            "severity": "important",
            "dimension": "comparison",
            "code": "ANCHORS_MODIFIED",
            "message": f"{len(anchor_changes)} URL(s) avec ancre modifiée",
            "detail": (
                "Changer l'ancre modifie le signal SEO pour la page cible. "
                "Selon First Link Priority (Matt Cutts 2009), l'ancre du menu est souvent "
                "la première que Google voit pour l'URL. Vérifier que les nouvelles ancres "
                "sont optimisées pour les mots-clés cibles."
            ),
            "evidence": [f"{c['url']}: {c['before']} → {c['after']}" for c in anchor_changes[:10]],
        })

    if depth_changes:
        deeper = [c for c in depth_changes if c["delta"] > 0]
        if deeper:
            issues.append({
                "severity": "important",
                "dimension": "comparison",
                "code": "PAGES_DEEPER_IN_NAV",
                "message": f"{len(deeper)} URL(s) enterrée(s) plus profond",
                "detail": (
                    "Une page plus profonde dans le menu reçoit moins d'équité et est moins "
                    "susceptible d'être crawlée fréquemment. Vérifier que les pages stratégiques "
                    "restent en position 1 ou 2."
                ),
                "evidence": [f"{c['url']}: depth {c['before_depth']} → {c['after_depth']}" for c in deeper[:10]],
            })

    for regression in semantic_regressions:
        issues.append({
            "severity": "important",
            "dimension": "comparison",
            "code": f"REGRESSION_{regression['type'].upper()}",
            "message": regression["detail"],
            "detail": "Régression sémantique par rapport à la version avant.",
        })

    link_ratio = (after_total / before_total) if before_total > 0 else 1.0
    if link_ratio < 0.5:
        issues.append({
            "severity": "critique",
            "dimension": "comparison",
            "code": "HALF_OF_LINKS_REMOVED",
            "message": f"Le nouveau menu contient {after_total} liens vs {before_total} avant (-{int((1-link_ratio)*100)}%)",
            "detail": (
                "Réduction majeure du maillage interne depuis la homepage. "
                "Si beaucoup de pages stratégiques sont concernées, impact SEO significatif. "
                "Rappel du cas Sitebulb (Dena Warren, août 2025) : -70% de trafic en un mois "
                "suite à une refonte de menu non validée."
            ),
        })

    # Verdict
    if any(i["severity"] == "bloquant" for i in issues):
        verdict = "BLOQUANT"
    elif any(i["severity"] == "critique" for i in issues):
        verdict = "CRITIQUE"
    elif any(i["severity"] == "important" for i in issues):
        verdict = "ATTENTION"
    else:
        verdict = "OK"

    result = {
        "meta": {
            "compared_at": datetime.now().isoformat(),
            "before_label": args.before_label,
            "after_label": args.after_label,
            "before_file": str(before_path),
            "after_file": str(after_path),
        },
        "url_diff": {
            "added": sorted(list(added)),
            "removed": sorted(list(removed)),
            "kept_count": len(kept),
            "total_before": before_total,
            "total_after": after_total,
            "net_change": after_total - before_total,
        },
        "anchor_changes": anchor_changes,
        "depth_changes": depth_changes,
        "semantic_regressions": semantic_regressions,
        "issues": issues,
        "verdict": verdict,
    }

    json_str = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_str, encoding="utf-8")
        print(f"[compare] ✓ {out}", file=sys.stderr)
        print(
            f"[compare]   before={before_total} links | after={after_total} | "
            f"added={len(added)} | removed={len(removed)} | verdict={verdict}",
            file=sys.stderr,
        )
    else:
        print(json_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
