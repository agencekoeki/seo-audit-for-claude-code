#!/usr/bin/env python3
"""
i18n_checks.py — Vérifie la cohérence hreflang et sélecteur de langue.

1. Détecte le sélecteur de langue dans le menu (heuristiques : liens ISO, drapeaux)
2. Parse les balises <link rel="alternate" hreflang="...">
3. Vérifie la cohérence bidirectionnelle sélecteur ↔ hreflang
4. Vérifie le self-referencing hreflang
5. Vérifie la présence de x-default

Usage :
    python3 i18n_checks.py --input PAGE.html --url URL --output RESULTS.json

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


# Codes ISO 639-1 courants pour la détection de sélecteur de langue
ISO_LANG_CODES = {
    "fr", "en", "de", "es", "it", "pt", "nl", "pl", "ru", "ja", "zh", "ko",
    "ar", "sv", "da", "no", "fi", "cs", "sk", "hu", "ro", "bg", "hr", "sl",
    "el", "tr", "th", "vi", "id", "ms", "uk", "he", "hi", "bn",
}

# Patterns pour détecter les sélecteurs de langue
LANG_SELECTOR_PATTERNS = [
    re.compile(r'class="[^"]*lang[^"]*"', re.I),
    re.compile(r'class="[^"]*language[^"]*"', re.I),
    re.compile(r'class="[^"]*locale[^"]*"', re.I),
    re.compile(r'class="[^"]*i18n[^"]*"', re.I),
    re.compile(r'class="[^"]*flag[^"]*"', re.I),
]


class I18nHTMLParser(HTMLParser):
    """Extrait les hreflang et les sélecteurs de langue."""

    def __init__(self):
        super().__init__()
        self.hreflangs: list[dict] = []
        self.lang_selector_links: list[dict] = []
        self.html_lang: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr = {k: v for k, v in attrs}

        # HTML lang attribute
        if tag == "html" and "lang" in attr:
            self.html_lang = attr["lang"]

        # <link rel="alternate" hreflang="...">
        if tag == "link" and attr.get("rel") == "alternate" and "hreflang" in attr:
            self.hreflangs.append({
                "hreflang": attr["hreflang"],
                "href": attr.get("href", ""),
            })

        # Sélecteur de langue : liens avec code ISO court dans le href ou le texte
        if tag == "a" and "href" in attr:
            href = attr.get("href", "")
            raw_attrs = " ".join(f'{k}="{v}"' for k, v in attrs if v)

            is_lang_link = False
            # Heuristique 1 : href contient /fr/, /en/, etc.
            lang_match = re.search(r'/([a-z]{2})(?:/|$)', href)
            if lang_match and lang_match.group(1) in ISO_LANG_CODES:
                is_lang_link = True

            # Heuristique 2 : classes liées à la langue
            for pat in LANG_SELECTOR_PATTERNS:
                if pat.search(raw_attrs):
                    is_lang_link = True
                    break

            # Heuristique 3 : hreflang attribut sur le lien
            if "hreflang" in attr:
                is_lang_link = True

            if is_lang_link:
                self.lang_selector_links.append({
                    "href": href,
                    "hreflang_attr": attr.get("hreflang"),
                    "detected_lang": lang_match.group(1) if lang_match and lang_match.group(1) in ISO_LANG_CODES else None,
                })


def check_hreflang_self_reference(hreflangs: list[dict], current_url: str) -> dict:
    """7.1.2 : Chaque page doit avoir une balise hreflang pointant vers elle-même."""
    if not hreflangs:
        return {
            "test": "hreflang_self_reference",
            "checklist_id": "7.1.2",
            "passed": None,
            "detail": "Aucune balise hreflang trouvée (site probablement monolingue)",
            "severity": None,
        }

    norm_current = urlparse(current_url)
    current_path = norm_current.path.rstrip("/") or "/"

    self_ref_found = False
    for h in hreflangs:
        href_parsed = urlparse(h["href"])
        href_path = href_parsed.path.rstrip("/") or "/"
        if href_path == current_path and href_parsed.netloc in ("", norm_current.netloc):
            self_ref_found = True
            break

    return {
        "test": "hreflang_self_reference",
        "checklist_id": "7.1.2",
        "passed": self_ref_found,
        "hreflang_count": len(hreflangs),
        "severity": "CRITIQUE" if not self_ref_found else None,
    }


def check_x_default(hreflangs: list[dict]) -> dict:
    """7.1.3 : Présence de x-default si multilingue."""
    if not hreflangs:
        return {
            "test": "x_default",
            "checklist_id": "7.1.3",
            "passed": None,
            "detail": "Pas de hreflang, pas de x-default nécessaire",
            "severity": None,
        }

    has_x_default = any(h["hreflang"] == "x-default" for h in hreflangs)

    return {
        "test": "x_default",
        "checklist_id": "7.1.3",
        "passed": has_x_default,
        "severity": "RECOMMANDATION" if not has_x_default else None,
    }


def check_selector_hreflang_coherence(
    lang_selector_links: list[dict], hreflangs: list[dict]
) -> dict:
    """7.1.1 : Cohérence sélecteur de langue ↔ hreflang alternates."""
    if not lang_selector_links and not hreflangs:
        return {
            "test": "selector_hreflang_coherence",
            "checklist_id": "7.1.1",
            "passed": None,
            "detail": "Ni sélecteur de langue ni hreflang détectés (site monolingue)",
            "severity": None,
        }

    selector_langs = {l["detected_lang"] for l in lang_selector_links if l.get("detected_lang")}
    hreflang_langs = {h["hreflang"].split("-")[0] for h in hreflangs if h["hreflang"] != "x-default"}

    in_selector_not_hreflang = selector_langs - hreflang_langs
    in_hreflang_not_selector = hreflang_langs - selector_langs

    issues = []
    if in_selector_not_hreflang:
        issues.append(f"Langues dans le sélecteur mais sans hreflang : {in_selector_not_hreflang}")
    if in_hreflang_not_selector:
        issues.append(f"Langues dans hreflang mais absentes du sélecteur : {in_hreflang_not_selector}")

    return {
        "test": "selector_hreflang_coherence",
        "checklist_id": "7.1.1",
        "passed": len(issues) == 0,
        "selector_langs": sorted(selector_langs),
        "hreflang_langs": sorted(hreflang_langs),
        "issues": issues,
        "severity": "IMPORTANT" if issues else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Checks i18n : hreflang + sélecteur de langue")
    parser.add_argument("--input", required=True, help="Fichier HTML à analyser")
    parser.add_argument("--url", required=True, help="URL de la page")
    parser.add_argument("--output", required=True, help="Fichier JSON de sortie")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[i18n_checks] ✗ Fichier introuvable : {args.input}", file=sys.stderr)
        return 1

    html = input_path.read_text(encoding="utf-8", errors="replace")
    print(f"[i18n_checks] Analyse de {args.input}...", file=sys.stderr)

    hp = I18nHTMLParser()
    hp.feed(html)

    tests = [
        check_selector_hreflang_coherence(hp.lang_selector_links, hp.hreflangs),
        check_hreflang_self_reference(hp.hreflangs, args.url),
        check_x_default(hp.hreflangs),
    ]

    is_multilingual = len(hp.hreflangs) > 0 or len(hp.lang_selector_links) > 0
    passed = sum(1 for t in tests if t.get("passed") is True)
    failed = sum(1 for t in tests if t.get("passed") is False)

    result = {
        "url": args.url,
        "input_file": args.input,
        "html_lang": hp.html_lang,
        "is_multilingual": is_multilingual,
        "hreflangs_found": len(hp.hreflangs),
        "lang_selector_links_found": len(hp.lang_selector_links),
        "tests": tests,
        "summary": {"total": len(tests), "passed": passed, "failed": failed},
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    label = "multilingue" if is_multilingual else "monolingue"
    print(f"[i18n_checks] ✓ Site {label}. {passed} passés, {failed} échoués. Résultat : {args.output}", file=sys.stderr)
    print(json.dumps({"is_multilingual": is_multilingual, "passed": passed, "failed": failed, "output_file": args.output}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[i18n_checks] ✗ Erreur inattendue : {e}", file=sys.stderr)
        sys.exit(3)
