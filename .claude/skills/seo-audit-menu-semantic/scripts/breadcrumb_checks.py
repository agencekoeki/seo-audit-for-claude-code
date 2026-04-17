#!/usr/bin/env python3
"""
breadcrumb_checks.py — Analyse les breadcrumbs HTML et JSON-LD BreadcrumbList.

Vérifie :
- Pattern ARIA correct (nav aria-label=breadcrumb, ol, aria-current sur dernier)
- JSON-LD BreadcrumbList valide (positions, URLs absolues, noms)
- Alignement HTML ↔ JSON-LD (mêmes entrées, mêmes noms, mêmes URLs)

Usage :
    python3 breadcrumb_checks.py --input PAGE.html --url URL --output RESULTS.json

Codes de sortie :
    0 : succès
    1 : fichier introuvable
    3 : erreur inattendue
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


class BreadcrumbHTMLParser(HTMLParser):
    """Extrait les breadcrumbs HTML et les blocs JSON-LD."""

    def __init__(self):
        super().__init__()
        self.breadcrumb_navs: list[dict] = []
        self.in_breadcrumb_nav = False
        self.in_ol = False
        self.in_li = False
        self.current_items: list[dict] = []
        self.current_link: dict | None = None
        self.current_text = ""
        self.json_ld_blocks: list[str] = []
        self.in_json_ld = False
        self.json_ld_buffer = ""
        self.has_aria_current_on_last = False
        self.uses_ol = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr = {k: v for k, v in attrs}

        # Détecter nav avec aria-label contenant "breadcrumb"
        if tag == "nav":
            label = (attr.get("aria-label", "") or "").lower()
            labelledby = attr.get("aria-labelledby", "")
            if "breadcrumb" in label or "fil d" in label or "ariane" in label:
                self.in_breadcrumb_nav = True
                self.current_items = []
                self.uses_ol = False
                self.has_aria_current_on_last = False

        if self.in_breadcrumb_nav:
            if tag == "ol":
                self.in_ol = True
                self.uses_ol = True
            if tag in ("li",) and self.in_ol:
                self.in_li = True
                self.current_text = ""
            if tag == "a" and self.in_li:
                self.current_link = {"href": attr.get("href", ""), "text": ""}
                if attr.get("aria-current") == "page":
                    self.has_aria_current_on_last = True

        # JSON-LD
        if tag == "script" and attr.get("type") == "application/ld+json":
            self.in_json_ld = True
            self.json_ld_buffer = ""

    def handle_endtag(self, tag: str):
        if self.in_breadcrumb_nav:
            if tag == "a" and self.current_link:
                self.current_link["text"] = self.current_text.strip()
                self.current_link = None
            if tag == "li" and self.in_li:
                text = self.current_text.strip()
                if text:
                    self.current_items.append({
                        "text": text,
                        "href": self.current_link["href"] if self.current_link else None,
                    })
                self.in_li = False
                self.current_text = ""
            if tag == "ol":
                self.in_ol = False
            if tag == "nav":
                self.breadcrumb_navs.append({
                    "items": self.current_items,
                    "uses_ol": self.uses_ol,
                    "aria_current_on_last": self.has_aria_current_on_last,
                })
                self.in_breadcrumb_nav = False

        if tag == "script" and self.in_json_ld:
            self.in_json_ld = False
            self.json_ld_blocks.append(self.json_ld_buffer)

    def handle_data(self, data: str):
        if self.in_json_ld:
            self.json_ld_buffer += data
        if self.in_breadcrumb_nav and (self.in_li or self.current_link):
            self.current_text += data


def extract_breadcrumb_jsonld(json_ld_blocks: list[str]) -> list[dict]:
    """Extrait les BreadcrumbList des blocs JSON-LD."""
    results = []
    for block in json_ld_blocks:
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue

        # Gérer @graph
        items_to_check = [data]
        if isinstance(data, list):
            items_to_check = data
        elif isinstance(data, dict) and "@graph" in data:
            items_to_check = data["@graph"]

        for item in items_to_check:
            if isinstance(item, dict) and item.get("@type") == "BreadcrumbList":
                list_elements = item.get("itemListElement", [])
                entries = []
                issues = []
                for el in list_elements:
                    pos = el.get("position")
                    name = el.get("name") or el.get("item", {}).get("name") if isinstance(el.get("item"), dict) else None
                    url = el.get("item") if isinstance(el.get("item"), str) else (el.get("item", {}).get("@id") if isinstance(el.get("item"), dict) else None)

                    if pos is None:
                        issues.append(f"Position manquante sur un élément")
                    if url and not url.startswith("http"):
                        issues.append(f"URL relative détectée : {url}")

                    entries.append({"position": pos, "name": name, "url": url})

                results.append({"entries": entries, "issues": issues})

    return results


def check_breadcrumb_html(navs: list[dict]) -> dict:
    """5.1.1 : Pattern ARIA correct."""
    if not navs:
        return {
            "test": "breadcrumb_html_pattern",
            "checklist_id": "5.1.1",
            "passed": None,
            "detail": "Aucun nav breadcrumb détecté (aria-label contenant 'breadcrumb'/'ariane')",
            "severity": None,
        }

    nav = navs[0]
    issues = []
    if not nav["uses_ol"]:
        issues.append("Breadcrumb n'utilise pas <ol> (recommandé pour l'ordre sémantique)")
    if not nav["aria_current_on_last"]:
        issues.append("Dernier item sans aria-current='page'")

    return {
        "test": "breadcrumb_html_pattern",
        "checklist_id": "5.1.1",
        "passed": len(issues) == 0,
        "items_count": len(nav["items"]),
        "uses_ol": nav["uses_ol"],
        "aria_current_on_last": nav["aria_current_on_last"],
        "issues": issues,
        "severity": "IMPORTANT" if issues else None,
    }


def check_breadcrumb_jsonld(jsonld_breadcrumbs: list[dict]) -> dict:
    """5.2.1 + 5.2.3 : JSON-LD BreadcrumbList valide, URLs absolues."""
    if not jsonld_breadcrumbs:
        return {
            "test": "breadcrumb_jsonld",
            "checklist_id": "5.2.1",
            "passed": None,
            "detail": "Aucun JSON-LD BreadcrumbList trouvé",
            "severity": "RECOMMANDATION",
        }

    bc = jsonld_breadcrumbs[0]
    has_relative_urls = any("URL relative" in i for i in bc["issues"])

    return {
        "test": "breadcrumb_jsonld",
        "checklist_id": "5.2.1 + 5.2.3",
        "passed": len(bc["issues"]) == 0,
        "entries_count": len(bc["entries"]),
        "entries": bc["entries"],
        "issues": bc["issues"],
        "severity": "CRITIQUE" if has_relative_urls else ("IMPORTANT" if bc["issues"] else None),
    }


def check_alignment(navs: list[dict], jsonld_breadcrumbs: list[dict]) -> dict:
    """5.2.2 : Alignement HTML ↔ JSON-LD."""
    if not navs or not jsonld_breadcrumbs:
        return {
            "test": "breadcrumb_alignment",
            "checklist_id": "5.2.2",
            "passed": None,
            "detail": "Impossible de comparer : HTML ou JSON-LD manquant",
            "severity": None,
        }

    html_items = navs[0]["items"]
    jsonld_entries = jsonld_breadcrumbs[0]["entries"]

    mismatches = []
    max_len = max(len(html_items), len(jsonld_entries))
    for i in range(max_len):
        html_name = html_items[i]["text"] if i < len(html_items) else None
        jsonld_name = jsonld_entries[i]["name"] if i < len(jsonld_entries) else None

        if html_name and jsonld_name and html_name.lower().strip() != jsonld_name.lower().strip():
            mismatches.append({
                "position": i + 1,
                "html_name": html_name,
                "jsonld_name": jsonld_name,
            })
        elif (html_name is None) != (jsonld_name is None):
            mismatches.append({
                "position": i + 1,
                "html_name": html_name,
                "jsonld_name": jsonld_name,
                "issue": "Présent dans un format mais absent de l'autre",
            })

    return {
        "test": "breadcrumb_alignment",
        "checklist_id": "5.2.2",
        "passed": len(mismatches) == 0 and len(html_items) == len(jsonld_entries),
        "html_count": len(html_items),
        "jsonld_count": len(jsonld_entries),
        "mismatches": mismatches,
        "severity": "IMPORTANT" if mismatches else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyse des breadcrumbs HTML + JSON-LD")
    parser.add_argument("--input", required=True, help="Fichier HTML à analyser")
    parser.add_argument("--url", required=True, help="URL de la page")
    parser.add_argument("--output", required=True, help="Fichier JSON de sortie")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[breadcrumb_checks] ✗ Fichier introuvable : {args.input}", file=sys.stderr)
        return 1

    html = input_path.read_text(encoding="utf-8", errors="replace")
    print(f"[breadcrumb_checks] Analyse de {args.input}...", file=sys.stderr)

    hp = BreadcrumbHTMLParser()
    hp.feed(html)

    jsonld_breadcrumbs = extract_breadcrumb_jsonld(hp.json_ld_blocks)

    tests = [
        check_breadcrumb_html(hp.breadcrumb_navs),
        check_breadcrumb_jsonld(jsonld_breadcrumbs),
        check_alignment(hp.breadcrumb_navs, jsonld_breadcrumbs),
    ]

    passed = sum(1 for t in tests if t.get("passed") is True)
    failed = sum(1 for t in tests if t.get("passed") is False)

    result = {
        "url": args.url,
        "input_file": args.input,
        "tests": tests,
        "summary": {"total": len(tests), "passed": passed, "failed": failed},
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[breadcrumb_checks] ✓ {passed} passés, {failed} échoués. Résultat : {args.output}", file=sys.stderr)
    print(json.dumps({"passed": passed, "failed": failed, "output_file": args.output}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[breadcrumb_checks] ✗ Erreur inattendue : {e}", file=sys.stderr)
        sys.exit(3)
