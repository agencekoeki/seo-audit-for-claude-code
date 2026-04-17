#!/usr/bin/env python3
"""
css_analyzer.py — Analyse sommaire des feuilles CSS pour détecter les patterns hostiles au mobile-first.

Détecte :
- nav { display: none } sans contexte (menu caché par défaut)
- Media queries min-width qui révèlent le nav (desktop-first caché)
- :hover sans :focus-within équivalent sur items nav
- Inline styles sur <link> CSS pour estimer la taille du payload CSS header

Usage :
    python3 css_analyzer.py --input PAGE.html --output RESULTS.json

Codes de sortie :
    0 : succès
    1 : fichier introuvable
    3 : erreur inattendue
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class CSSExtractor(HTMLParser):
    """Extrait les blocs <style> et les URLs des <link rel=stylesheet>."""

    def __init__(self):
        super().__init__()
        self.inline_styles: list[str] = []
        self.stylesheet_urls: list[str] = []
        self.in_style = False
        self.style_buffer = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr = {k: v for k, v in attrs}
        if tag == "style":
            self.in_style = True
            self.style_buffer = ""
        if tag == "link" and attr.get("rel") == "stylesheet" and "href" in attr:
            self.stylesheet_urls.append(attr["href"])

    def handle_endtag(self, tag: str):
        if tag == "style" and self.in_style:
            self.in_style = False
            self.inline_styles.append(self.style_buffer)

    def handle_data(self, data: str):
        if self.in_style:
            self.style_buffer += data


def check_nav_hidden_by_default(css_text: str) -> dict:
    """1.5.3 : Détecte nav { display: none } hors media query (caché par défaut)."""
    # Chercher des règles qui cachent le nav hors media query
    # On cherche nav.*display\s*:\s*none en dehors de @media
    # Approche simplifiée : chercher nav.*display:none dans le CSS global
    nav_hidden_patterns = [
        re.compile(r'nav\s*\{[^}]*display\s*:\s*none', re.I | re.S),
        re.compile(r'\.nav[^{]*\{[^}]*display\s*:\s*none', re.I | re.S),
        re.compile(r'\[role=["\']navigation["\']\]\s*\{[^}]*display\s*:\s*none', re.I | re.S),
    ]

    # Extraire les blocs media query pour les exclure
    media_blocks = re.findall(r'@media[^{]*\{(?:[^{}]*\{[^}]*\})*[^}]*\}', css_text, re.S)
    css_without_media = css_text
    for block in media_blocks:
        css_without_media = css_without_media.replace(block, "")

    findings = []
    for pat in nav_hidden_patterns:
        matches = pat.findall(css_without_media)
        if matches:
            findings.extend(m.strip()[:100] for m in matches)

    return {
        "test": "nav_hidden_by_default",
        "checklist_id": "1.5.3",
        "passed": len(findings) == 0,
        "findings": findings[:3],
        "detail": "Le nav est caché par défaut (display:none) hors media query — hostile au mobile-first" if findings else None,
        "severity": "IMPORTANT" if findings else None,
    }


def check_desktop_first_media_queries(css_text: str) -> dict:
    """1.5.3 : Détecte les media queries min-width qui révèlent le nav (desktop-first)."""
    # Pattern : @media (min-width: Xpx) { ... nav ... display: block/flex ... }
    media_min_width = re.findall(
        r'@media[^{]*min-width\s*:\s*(\d+)px[^{]*\{((?:[^{}]*\{[^}]*\})*[^}]*)\}',
        css_text, re.S
    )

    desktop_first_signals = []
    for breakpoint, content in media_min_width:
        bp = int(breakpoint)
        if bp >= 640:  # Tailwind sm=640, md=768, lg=1024
            # Chercher si le contenu révèle un nav
            nav_reveal = re.search(r'nav[^{]*\{[^}]*display\s*:\s*(?:block|flex|grid)', content, re.I | re.S)
            if nav_reveal:
                desktop_first_signals.append({
                    "breakpoint_px": bp,
                    "snippet": nav_reveal.group(0).strip()[:100],
                })

    return {
        "test": "desktop_first_media_queries",
        "checklist_id": "1.5.3",
        "passed": len(desktop_first_signals) == 0,
        "signals": desktop_first_signals[:3],
        "detail": "Media queries min-width révèlent le nav — pattern desktop-first" if desktop_first_signals else None,
        "severity": "IMPORTANT" if desktop_first_signals else None,
    }


def check_hover_without_focus(css_text: str) -> dict:
    """3.2.2 : Détecte :hover sur items nav sans :focus-within ou :focus équivalent."""
    # Chercher les sélecteurs nav.*:hover
    hover_rules = re.findall(r'(nav[^{]*:hover[^{]*)\{', css_text, re.I)
    focus_rules = re.findall(r'(nav[^{]*:focus(?:-within|-visible)?[^{]*)\{', css_text, re.I)

    hover_selectors = {r.strip().replace(":hover", "") for r in hover_rules}
    focus_selectors = {r.strip().replace(":focus-within", "").replace(":focus-visible", "").replace(":focus", "") for r in focus_rules}

    hover_only = hover_selectors - focus_selectors

    return {
        "test": "hover_without_focus",
        "checklist_id": "3.2.2",
        "passed": len(hover_only) == 0,
        "hover_rules_count": len(hover_rules),
        "focus_rules_count": len(focus_rules),
        "hover_only_selectors": [s[:80] for s in list(hover_only)[:5]],
        "severity": "IMPORTANT" if hover_only else None,
    }


def check_css_payload(extractor: CSSExtractor) -> dict:
    """Estimation du poids CSS dans le header (inline + nombre de feuilles externes)."""
    inline_total = sum(len(s.encode("utf-8")) for s in extractor.inline_styles)
    external_count = len(extractor.stylesheet_urls)

    return {
        "test": "css_payload_estimate",
        "checklist_id": "4.3.2",
        "inline_css_bytes": inline_total,
        "external_stylesheets_count": external_count,
        "inline_css_heavy": inline_total > 50000,
        "detail": f"CSS inline : {inline_total} octets, {external_count} feuilles externes" if inline_total > 50000 else None,
        "severity": "RECOMMANDATION" if inline_total > 50000 else None,
    }


USER_AGENT = (
    "Mozilla/5.0 (compatible; seo-audit-for-claude-code/0.3; "
    "+https://github.com/agencekoeki/seo-audit-for-claude-code)"
)

MAX_EXTERNAL_SHEETS = 5
FETCH_TIMEOUT = 5


def fetch_external_css(urls: list[str], base_url: str, insecure: bool = False) -> list[dict]:
    """Fetch les premières feuilles CSS externes (max MAX_EXTERNAL_SHEETS).

    Retourne une liste de {url, css_text, size_bytes, error}.
    """
    ctx = None
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    results = []
    for href in urls[:MAX_EXTERNAL_SHEETS]:
        # Résoudre les URLs relatives
        full_url = urljoin(base_url, href)
        entry = {"url": full_url, "css_text": None, "size_bytes": 0, "error": None}
        try:
            req = Request(full_url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=FETCH_TIMEOUT, context=ctx) as resp:
                raw = resp.read()
                entry["css_text"] = raw.decode("utf-8", errors="replace")
                entry["size_bytes"] = len(raw)
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            entry["error"] = str(getattr(e, "reason", e))
            print(f"[css_analyzer]   ⚠ Impossible de fetcher {full_url} : {entry['error']}", file=sys.stderr)
        results.append(entry)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyse CSS pour patterns hostiles au mobile-first")
    parser.add_argument("--input", required=True, help="Fichier HTML à analyser")
    parser.add_argument("--output", required=True, help="Fichier JSON de sortie")
    parser.add_argument("--base-url", default="", help="URL de base pour résoudre les chemins CSS relatifs")
    parser.add_argument("--insecure", action="store_true", help="Ignorer les erreurs SSL")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[css_analyzer] ✗ Fichier introuvable : {args.input}", file=sys.stderr)
        return 1

    html = input_path.read_text(encoding="utf-8", errors="replace")
    print(f"[css_analyzer] Analyse CSS de {args.input}...", file=sys.stderr)

    extractor = CSSExtractor()
    extractor.feed(html)

    # Fetch les feuilles CSS externes (max 5, ordonnées par apparition dans le HTML)
    external_sheets = []
    if extractor.stylesheet_urls and args.base_url:
        print(f"[css_analyzer]   Fetch de {min(len(extractor.stylesheet_urls), MAX_EXTERNAL_SHEETS)} feuille(s) CSS externe(s)...", file=sys.stderr)
        external_sheets = fetch_external_css(extractor.stylesheet_urls, args.base_url, insecure=args.insecure)

    # Concaténer tout le CSS : inline + externe
    all_css_parts = list(extractor.inline_styles)
    for sheet in external_sheets:
        if sheet["css_text"]:
            all_css_parts.append(sheet["css_text"])

    css_text = "\n".join(all_css_parts)

    tests = [
        check_nav_hidden_by_default(css_text),
        check_desktop_first_media_queries(css_text),
        check_hover_without_focus(css_text),
        check_css_payload(extractor),
    ]

    passed = sum(1 for t in tests if t.get("passed") is True)
    failed = sum(1 for t in tests if t.get("passed") is False)

    result = {
        "input_file": args.input,
        "tests": tests,
        "summary": {"total": len(tests), "passed": passed, "failed": failed},
        "external_sheets_fetched": len([s for s in external_sheets if s["css_text"]]),
        "external_sheets_failed": len([s for s in external_sheets if s["error"]]),
        "note": f"CSS analysé : {len(extractor.inline_styles)} bloc(s) inline + {len([s for s in external_sheets if s['css_text']])} feuille(s) externe(s) sur {len(extractor.stylesheet_urls)} détectée(s).",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[css_analyzer] ✓ {passed} passés, {failed} échoués. Résultat : {args.output}", file=sys.stderr)
    print(json.dumps({"passed": passed, "failed": failed, "output_file": args.output}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[css_analyzer] ✗ Erreur inattendue : {e}", file=sys.stderr)
        sys.exit(3)
