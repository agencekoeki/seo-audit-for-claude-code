#!/usr/bin/env python3
"""
accessibility_checks.py — Checks statiques d'accessibilité ARIA/WCAG sur le HTML.

Détecte les anti-patterns courants sans exécution JS :
- Anti-pattern role="menu" / role="menubar" sur nav de site
- Landmarks nav multiples sans labels uniques
- aria-current="page" absent sur l'item actif
- Focus visible supprimé (outline:none sans remplacement)
- Skip link absent ou cassé
- Triggers de sous-menu : <button> vs <a> vs <div>

Usage :
    python3 accessibility_checks.py --input PAGE.html --url URL --output RESULTS.json

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
from typing import Any


class AccessibilityHTMLParser(HTMLParser):
    """Parse le HTML pour extraire les éléments pertinents à l'accessibilité."""

    def __init__(self):
        super().__init__()
        self.navs: list[dict] = []
        self.nav_depth = 0
        self.current_nav: dict | None = None
        self.links_in_nav: list[dict] = []
        self.buttons_in_nav: list[dict] = []
        self.role_menu_in_nav: list[dict] = []
        self.all_focusable: list[dict] = []
        self.style_blocks: list[str] = []
        self.in_style = False
        self.skip_link_candidates: list[dict] = []
        self.ids_found: set[str] = set()
        self.first_focusable_seen = False
        self.element_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_dict = {k: v for k, v in attrs}
        self.element_count += 1

        # Collecter les IDs
        if "id" in attr_dict and attr_dict["id"]:
            self.ids_found.add(attr_dict["id"])

        # Détecter les <nav> et role="navigation"
        if tag == "nav" or attr_dict.get("role") == "navigation":
            self.nav_depth += 1
            self.current_nav = {
                "tag": tag,
                "aria_label": attr_dict.get("aria-label"),
                "aria_labelledby": attr_dict.get("aria-labelledby"),
                "role": attr_dict.get("role"),
                "line": self.getpos()[0],
            }
            self.navs.append(self.current_nav)

        # Dans un nav : collecter liens, boutons, roles ARIA
        if self.nav_depth > 0:
            if tag == "a":
                href = attr_dict.get("href", "")
                self.links_in_nav.append({
                    "href": href,
                    "aria_current": attr_dict.get("aria-current"),
                    "aria_label": attr_dict.get("aria-label"),
                    "role": attr_dict.get("role"),
                    "line": self.getpos()[0],
                })

            if tag == "button":
                self.buttons_in_nav.append({
                    "aria_expanded": attr_dict.get("aria-expanded"),
                    "aria_controls": attr_dict.get("aria-controls"),
                    "aria_haspopup": attr_dict.get("aria-haspopup"),
                    "line": self.getpos()[0],
                })

            role = attr_dict.get("role", "")
            if role in ("menu", "menubar", "menuitem"):
                self.role_menu_in_nav.append({
                    "tag": tag,
                    "role": role,
                    "line": self.getpos()[0],
                })

        # Premier élément focusable (skip link check)
        if tag in ("a", "button", "input") and not self.first_focusable_seen:
            self.first_focusable_seen = True
            href = attr_dict.get("href", "")
            self.skip_link_candidates.append({
                "tag": tag,
                "href": href,
                "is_skip_link": tag == "a" and href.startswith("#"),
                "target_id": href.lstrip("#") if href.startswith("#") else None,
                "line": self.getpos()[0],
            })

        # Éléments avec aria-expanded (triggers de sous-menu)
        if attr_dict.get("aria-expanded") is not None:
            self.all_focusable.append({
                "tag": tag,
                "aria_expanded": attr_dict.get("aria-expanded"),
                "aria_controls": attr_dict.get("aria-controls"),
                "is_button": tag == "button",
                "is_anchor": tag == "a",
                "is_div_span": tag in ("div", "span"),
                "line": self.getpos()[0],
            })

        # Blocs <style>
        if tag == "style":
            self.in_style = True

    def handle_endtag(self, tag: str):
        if tag == "nav":
            self.nav_depth = max(0, self.nav_depth - 1)
            if self.nav_depth == 0:
                self.current_nav = None
        if tag == "style":
            self.in_style = False

    def handle_data(self, data: str):
        if self.in_style:
            self.style_blocks.append(data)


def check_nav_landmarks(parser: AccessibilityHTMLParser) -> dict:
    """3.1.1 + 3.1.3 : Présence de <nav>, labels uniques si multiples."""
    navs = parser.navs
    if len(navs) == 0:
        return {
            "test": "nav_landmarks",
            "wcag": "1.3.1",
            "passed": False,
            "detail": "Aucun élément <nav> ou role='navigation' trouvé",
            "severity": "CRITIQUE",
        }

    labels = [n.get("aria_label") or n.get("aria_labelledby") for n in navs]
    has_labels = all(l for l in labels)
    unique_labels = len(set(l for l in labels if l)) == len([l for l in labels if l])

    issues = []
    if len(navs) > 1 and not has_labels:
        issues.append("Navs multiples sans aria-label unique sur chacun")
    if len(navs) > 1 and has_labels and not unique_labels:
        issues.append("Navs multiples avec des aria-label identiques")
    if len(navs) > 3:
        issues.append(f"{len(navs)} navs détectés (recommandé : max 3)")

    return {
        "test": "nav_landmarks",
        "wcag": "1.3.1 + ARIA landmarks",
        "passed": len(issues) == 0,
        "elements_checked": len(navs),
        "nav_count": len(navs),
        "labels": labels,
        "issues": issues,
        "severity": "IMPORTANT" if issues else None,
    }


def check_role_menu_antipattern(parser: AccessibilityHTMLParser) -> dict:
    """3.1.2 : Anti-pattern role='menu'/menubar/menuitem dans la nav de site."""
    violations = parser.role_menu_in_nav
    return {
        "test": "role_menu_antipattern",
        "wcag": "ARIA APG",
        "passed": len(violations) == 0,
        "elements_checked": len(parser.links_in_nav) + len(parser.buttons_in_nav),
        "violations_count": len(violations),
        "violations": violations[:5],
        "detail": "role='menu'/'menubar'/'menuitem' sont pour les menus d'APPLICATION, pas pour la navigation de site" if violations else None,
        "severity": "CRITIQUE" if violations else None,
    }


def check_aria_current(parser: AccessibilityHTMLParser, current_url: str) -> dict:
    """3.1.4 : aria-current='page' sur l'item correspondant à l'URL courante."""
    from urllib.parse import urlparse

    current_path = urlparse(current_url).path.rstrip("/") or "/"

    matching_links = []
    aria_current_found = False
    for link in parser.links_in_nav:
        href = link.get("href", "")
        try:
            link_path = urlparse(href).path.rstrip("/") or "/"
        except Exception:
            continue
        if link_path == current_path:
            matching_links.append(link)
            if link.get("aria_current") == "page":
                aria_current_found = True

    return {
        "test": "aria_current_page",
        "wcag": "ARIA best practice",
        "passed": not matching_links or aria_current_found,
        "elements_checked": len(parser.links_in_nav),
        "current_path": current_path,
        "matching_links_count": len(matching_links),
        "aria_current_present": aria_current_found,
        "severity": "IMPORTANT" if matching_links and not aria_current_found else None,
    }


def check_focus_visible_css(parser: AccessibilityHTMLParser) -> dict:
    """3.2.4 : Détecte outline:none ou outline:0 dans les styles sans remplacement."""
    css_text = "\n".join(parser.style_blocks)
    outline_none = re.findall(r'outline\s*:\s*(?:none|0)\b', css_text, re.IGNORECASE)
    focus_styling = re.findall(r':focus(?:-visible|-within)?\s*\{[^}]*(?:outline|box-shadow|border)', css_text, re.IGNORECASE)

    suppressed = len(outline_none) > 0
    has_replacement = len(focus_styling) > 0

    return {
        "test": "focus_visible_css",
        "wcag": "2.4.7",
        "passed": not suppressed or has_replacement,
        "elements_checked": len(parser.style_blocks),
        "outline_none_found": len(outline_none),
        "focus_styling_found": len(focus_styling),
        "detail": "outline:none détecté sans :focus styling de remplacement" if suppressed and not has_replacement else None,
        "severity": "CRITIQUE" if suppressed and not has_replacement else None,
    }


def check_skip_link(parser: AccessibilityHTMLParser) -> dict:
    """3.3.1 : Skip link comme premier élément focusable."""
    if not parser.skip_link_candidates:
        return {
            "test": "skip_link",
            "wcag": "2.4.1",
            "passed": False,
            "elements_checked": 0,
            "detail": "Aucun élément focusable trouvé en début de page",
            "severity": "CRITIQUE",
        }

    first = parser.skip_link_candidates[0]
    target_exists = first.get("target_id") in parser.ids_found if first.get("target_id") else False

    return {
        "test": "skip_link",
        "wcag": "2.4.1",
        "passed": first["is_skip_link"] and target_exists,
        "elements_checked": 1,
        "first_focusable": first,
        "target_exists": target_exists,
        "severity": "CRITIQUE" if not first["is_skip_link"] else ("IMPORTANT" if not target_exists else None),
    }


def check_trigger_elements(parser: AccessibilityHTMLParser) -> dict:
    """3.4.2 : Les triggers de sous-menu doivent être des <button>, pas des <a> ou <div>."""
    triggers = parser.all_focusable
    violations = [t for t in triggers if not t["is_button"]]

    return {
        "test": "trigger_elements",
        "wcag": "4.1.2",
        "passed": len(violations) == 0,
        "elements_checked": len(triggers),
        "total_triggers": len(triggers),
        "violations_count": len(violations),
        "violations": [
            {"tag": v["tag"], "aria_controls": v.get("aria_controls"), "line": v["line"]}
            for v in violations[:5]
        ],
        "severity": "IMPORTANT" if violations else None,
    }


def detect_fake_links(html: str) -> dict:
    """Détecte les faux liens dans la nav (onclick, data-href, javascript:void, <a> sans href)."""
    fake_links: list[dict] = []

    # Pattern 1 : éléments non-<a> avec onclick dans nav
    for m in re.finditer(
        r'<(div|span|button|li)\b[^>]*onclick\s*=\s*["\']([^"\']*(?:location|navigate|router|goto|href)[^"\']*)["\'][^>]*>',
        html, re.I,
    ):
        fake_links.append({
            "element": m.group(1),
            "pattern": "onclick_navigation",
            "onclick_content": m.group(2)[:120],
            "severity": "CRITIQUE",
        })

    # Pattern 2 : <a> avec data-href ou data-url mais sans vrai href
    for m in re.finditer(r'<a\b(?=[^>]*data-(?:href|url)\s*=)(?![^>]*\bhref\s*=)[^>]*>', html, re.I):
        fake_links.append({
            "element": "a",
            "pattern": "data_href_no_real_href",
            "snippet": m.group(0)[:120],
            "severity": "CRITIQUE",
        })

    # Pattern 3 : <a href="javascript:void(0)"> ou <a href="javascript:">
    for m in re.finditer(r'<a\b[^>]*href\s*=\s*["\']javascript:[^"\']*["\'][^>]*>', html, re.I):
        fake_links.append({
            "element": "a",
            "pattern": "javascript_void_href",
            "snippet": m.group(0)[:120],
            "severity": "CRITIQUE",
        })

    # Pattern 4 : <a href="#"> avec onclick
    for m in re.finditer(r'<a\b[^>]*href\s*=\s*["\']#["\'][^>]*onclick\s*=[^>]*>', html, re.I):
        fake_links.append({
            "element": "a",
            "pattern": "hash_href_with_onclick",
            "snippet": m.group(0)[:120],
            "severity": "CRITIQUE",
        })

    # Pattern 5 : <a> sans href du tout (mais avec onclick ou class de lien)
    for m in re.finditer(r'<a\b(?![^>]*\bhref\s*=)[^>]*onclick\s*=[^>]*>', html, re.I):
        fake_links.append({
            "element": "a",
            "pattern": "anchor_no_href_with_onclick",
            "snippet": m.group(0)[:120],
            "severity": "CRITIQUE",
        })

    # Pattern 6 : Framework-specific — Angular routerLink, Vue :href/v-bind:href sans vrai href
    # Google mentionne explicitement <a routerLink="..."> comme non-crawlable
    for m in re.finditer(
        r'<a\b(?=[^>]*(?:routerLink|v-bind:href|\[routerLink\]|:href)\s*=)(?![^>]*\bhref\s*=)[^>]*>',
        html,
    ):
        fake_links.append({
            "element": "a",
            "pattern": "framework_binding_no_href",
            "snippet": m.group(0)[:120],
            "severity": "CRITIQUE",
            "reason": "Attribut framework (routerLink/v-bind:href) sans vrai href. Google ne peut pas crawler ce lien.",
        })

    return {
        "test": "fake_links",
        "standard": "Google Search Central — crawlable links",
        "passed": len(fake_links) == 0,
        "elements_checked": len(fake_links),  # nombre de faux liens trouvés
        "violations_count": len(fake_links),
        "violations": fake_links[:10],
        "severity": "CRITIQUE" if fake_links else None,
    }


def measure_header_weight(html: str) -> dict:
    """Mesure la taille du header et de ses composants (SVG inline, images, liens)."""
    header_match = re.search(r'<header[^>]*>(.*?)</header>', html, re.S | re.I)
    if not header_match:
        return {
            "test": "header_weight",
            "header_found": False,
            "elements_checked": 0,
            "severity": None,
        }

    header_html = header_match.group(0)
    header_bytes = len(header_html.encode("utf-8"))

    svg_matches = re.findall(r'<svg[^>]*>.*?</svg>', header_html, re.S | re.I)
    svg_count = len(svg_matches)
    svg_total_bytes = sum(len(s.encode("utf-8")) for s in svg_matches)

    img_count = len(re.findall(r'<img\b', header_html, re.I))
    link_count = len(re.findall(r'<a\b[^>]*href', header_html, re.I))

    severity = None
    if header_bytes > 50000:
        severity = "CRITIQUE"
    elif header_bytes > 20000:
        severity = "IMPORTANT"
    if svg_count > 30:
        severity = "CRITIQUE"
    elif svg_count > 10 and severity != "CRITIQUE":
        severity = "IMPORTANT"

    return {
        "test": "header_weight",
        "header_found": True,
        "elements_checked": 1,
        "header_bytes": header_bytes,
        "header_kb": round(header_bytes / 1024, 1),
        "svg_inline_count": svg_count,
        "svg_inline_bytes": svg_total_bytes,
        "svg_inline_kb": round(svg_total_bytes / 1024, 1),
        "img_count": img_count,
        "link_count": link_count,
        "passed": severity is None,
        "severity": severity,
        "detail": (
            f"Header de {round(header_bytes / 1024, 1)} KB dont "
            f"{round(svg_total_bytes / 1024, 1)} KB de SVG inline ({svg_count} SVG)"
        ) if severity else None,
    }


def check_base_href(html: str, expected_domain: str) -> dict:
    """Vérifie si un <base href> existe et s'il pointe vers le bon domaine."""
    from urllib.parse import urlparse

    base_match = re.search(
        r'<base[^>]*href\s*=\s*["\']([^"\']+)["\']', html, re.I
    )

    if not base_match:
        return {
            "test": "base_href",
            "base_href_present": False,
            "elements_checked": 0,
            "passed": True,
            "severity": None,
        }

    base_url = base_match.group(1)
    base_domain = urlparse(base_url).netloc
    expected = urlparse(expected_domain).netloc if "://" in expected_domain else expected_domain
    domain_match = base_domain == expected or base_domain == ""

    return {
        "test": "base_href",
        "base_href_present": True,
        "base_href_value": base_url,
        "base_domain": base_domain,
        "expected_domain": expected,
        "domain_match": domain_match,
        "elements_checked": 1,
        "passed": domain_match,
        "severity": "BLOQUANT" if not domain_match else None,
        "reason": (
            f"<base href> pointe vers {base_domain} au lieu de {expected}. "
            "Toutes les URLs relatives du menu sont résolues vers le mauvais domaine."
        ) if not domain_match else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Checks statiques d'accessibilité ARIA/WCAG")
    parser.add_argument("--input", required=True, help="Fichier HTML à analyser")
    parser.add_argument("--url", required=True, help="URL de la page (pour aria-current)")
    parser.add_argument("--output", required=True, help="Fichier JSON de sortie")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[accessibility_checks] ✗ Fichier introuvable : {args.input}", file=sys.stderr)
        return 1

    html = input_path.read_text(encoding="utf-8", errors="replace")

    print(f"[accessibility_checks] Analyse de {args.input} ({len(html)} chars)...", file=sys.stderr)

    hp = AccessibilityHTMLParser()
    hp.feed(html)

    tests = [
        check_nav_landmarks(hp),
        check_role_menu_antipattern(hp),
        check_aria_current(hp, args.url),
        check_focus_visible_css(hp),
        check_skip_link(hp),
        check_trigger_elements(hp),
        detect_fake_links(html),
        measure_header_weight(html),
        check_base_href(html, args.url),
    ]

    passed = sum(1 for t in tests if t.get("passed"))
    failed = sum(1 for t in tests if t.get("passed") is False)

    result = {
        "url": args.url,
        "input_file": args.input,
        "status": "complete",
        "tests": tests,
        "summary": {"total": len(tests), "passed": passed, "failed": failed},
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[accessibility_checks] ✓ {passed} passés, {failed} échoués. Résultat : {args.output}", file=sys.stderr)
    print(json.dumps({"passed": passed, "failed": failed, "output_file": args.output}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[accessibility_checks] ✗ Erreur inattendue : {e}", file=sys.stderr)
        sys.exit(3)
