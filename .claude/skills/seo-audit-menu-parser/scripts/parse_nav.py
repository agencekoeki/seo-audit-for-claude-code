#!/usr/bin/env python3
"""
parse_nav.py — Parser HTML de menu de navigation.

Extrait la structure d'un menu à partir d'un HTML brut et produit un JSON
structuré utilisable par les agents spécialisés de l'audit.

Principes :
- Parsing best-effort : jamais de crash silencieux, toujours un JSON produit
- Détection des patterns problématiques au fil du parsing
- Distinction stricte entre fait observable et interprétation

Usage :
    python3 parse_nav.py --html page.html --output parsed.json --label "Homepage"
    python3 parse_nav.py --stdin --output parsed.json
    cat page.html | python3 parse_nav.py --stdin
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from html.parser import HTMLParser
from dataclasses import dataclass, field, asdict
from collections import Counter
from pathlib import Path


PARSER_VERSION = "0.2.0"


@dataclass
class NavLink:
    """Un lien dans une navigation."""
    href: str = ""
    text: str = ""
    depth: int = 0
    rel: str = ""
    target: str = ""
    aria_label: str = ""
    aria_current: str = ""
    class_: str = ""
    title: str = ""
    onclick: str = ""
    raw_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["class"] = d.pop("class_")  # rename for JSON output
        return d


@dataclass
class NavElement:
    """Un élément <nav> détecté."""
    nav_index: int
    aria_label: str = ""
    aria_labelledby: str = ""
    role: str = ""
    id: str = ""
    class_: str = ""
    link_count: int = 0
    max_depth: int = 0
    uses_ul_li: bool = False
    links: list[NavLink] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nav_index": self.nav_index,
            "aria_label": self.aria_label,
            "aria_labelledby": self.aria_labelledby,
            "role": self.role,
            "id": self.id,
            "class": self.class_,
            "link_count": len(self.links),
            "max_depth": self.max_depth,
            "uses_ul_li": self.uses_ul_li,
            "links": [l.to_dict() for l in self.links],
        }


@dataclass
class Issue:
    severity: str
    dimension: str
    code: str
    message: str
    detail: str = ""
    url: str = ""
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class NavExtractor(HTMLParser):
    """Parser HTML stateful pour extraire la structure de navigation."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.navs: list[NavElement] = []
        self.issues: list[Issue] = []

        self.has_header = False
        self.has_main = False
        self.has_footer = False
        self.semantic_elements: set[str] = set()

        self.in_nav = False
        self.nav_depth = 0
        self.ul_depth = 0
        self.in_a = False
        self.in_header = False
        self.in_footer = False

        self.current_nav: NavElement | None = None
        self.current_link: NavLink | None = None

        self.total_links_in_doc = 0
        self.header_links = 0
        self.footer_links = 0

        self.malformed_detected = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: (v or "") for k, v in attrs}

        if tag in ("header", "main", "footer", "nav", "article", "section", "aside"):
            self.semantic_elements.add(tag)

        if tag == "header":
            self.has_header = True
            self.in_header = True
        elif tag == "main":
            self.has_main = True
        elif tag == "footer":
            self.has_footer = True
            self.in_footer = True

        if tag == "nav":
            self.in_nav = True
            self.nav_depth += 1
            nav_index = len(self.navs) + 1
            self.current_nav = NavElement(
                nav_index=nav_index,
                aria_label=attrs_dict.get("aria-label", ""),
                aria_labelledby=attrs_dict.get("aria-labelledby", ""),
                role=attrs_dict.get("role", ""),
                id=attrs_dict.get("id", ""),
                class_=attrs_dict.get("class", ""),
            )
            if not self.current_nav.aria_label and not self.current_nav.aria_labelledby:
                self.issues.append(Issue(
                    severity="important",
                    dimension="semantic_html",
                    code="NAV_NO_ARIA_LABEL",
                    message=f"<nav> #{nav_index} sans aria-label ni aria-labelledby",
                    detail=(
                        "Chaque <nav> devrait avoir un aria-label pour distinguer "
                        "les zones de navigation (ex: 'Navigation principale'). "
                        "WCAG 2.4.6 (niveau AA)."
                    ),
                ))

        if self.in_nav and self.current_nav is not None:
            if tag == "ul":
                self.ul_depth += 1
                self.current_nav.uses_ul_li = True
                if self.ul_depth > self.current_nav.max_depth:
                    self.current_nav.max_depth = self.ul_depth

            if tag == "a":
                self._start_link(attrs_dict)

            if tag == "div" and attrs_dict.get("onclick"):
                self.issues.append(Issue(
                    severity="bloquant",
                    dimension="semantic_html",
                    code="DIV_ONCLICK_AS_LINK",
                    message=f"<div onclick> utilisé comme lien dans nav #{self.current_nav.nav_index}",
                    detail="Un <div> avec onclick n'est pas un lien HTML. Googlebot ne le suit pas en première passe.",
                    evidence=f'<div onclick="{attrs_dict.get("onclick", "")[:80]}...">',
                ))

            if tag == "span" and attrs_dict.get("onclick"):
                self.issues.append(Issue(
                    severity="bloquant",
                    dimension="semantic_html",
                    code="SPAN_ONCLICK_AS_LINK",
                    message=f"<span onclick> utilisé comme lien dans nav #{self.current_nav.nav_index}",
                    detail="Un <span> avec onclick n'est pas un lien. Utiliser <a href>.",
                ))

        if tag == "a":
            self.total_links_in_doc += 1
            if self.in_header:
                self.header_links += 1
            if self.in_footer:
                self.footer_links += 1

    def _start_link(self, attrs_dict: dict[str, str]) -> None:
        if not self.current_nav:
            return
        self.in_a = True
        href = attrs_dict.get("href", "")
        self.current_link = NavLink(
            href=href,
            depth=self.ul_depth,
            rel=attrs_dict.get("rel", ""),
            target=attrs_dict.get("target", ""),
            aria_label=attrs_dict.get("aria-label", ""),
            aria_current=attrs_dict.get("aria-current", ""),
            class_=attrs_dict.get("class", ""),
            title=attrs_dict.get("title", ""),
            onclick=attrs_dict.get("onclick", ""),
        )

        nav_idx = self.current_nav.nav_index

        if not href:
            self.current_link.raw_issues.append("MISSING_HREF")
            self.issues.append(Issue(
                severity="bloquant",
                dimension="link_quality",
                code="MISSING_HREF",
                message=f"Lien sans href dans nav #{nav_idx}",
                detail="Un <a> sans href n'est pas un lien crawlable par Googlebot.",
            ))
        elif href == "#":
            self.current_link.raw_issues.append("HASH_ONLY")
            self.issues.append(Issue(
                severity="bloquant",
                dimension="link_quality",
                code="HASH_ONLY_HREF",
                message=f'Lien avec href="#" dans nav #{nav_idx}',
                detail='href="#" est un lien mort pour les crawlers.',
            ))
        elif href.startswith("javascript:"):
            self.current_link.raw_issues.append("JAVASCRIPT_HREF")
            self.issues.append(Issue(
                severity="bloquant",
                dimension="link_quality",
                code="JAVASCRIPT_HREF",
                message=f'Lien avec href="javascript:..." dans nav #{nav_idx}',
                detail="Les liens javascript: ne sont pas crawlables.",
                url=href,
            ))

        if self.current_link.onclick and not href:
            self.current_link.raw_issues.append("ONCLICK_NO_HREF")
            self.issues.append(Issue(
                severity="bloquant",
                dimension="js_crawlability",
                code="ONCLICK_NO_HREF",
                message=f"Lien avec onclick sans href dans nav #{nav_idx}",
                detail="Invisible pour Googlebot en première passe.",
            ))

        if "nofollow" in self.current_link.rel:
            self.current_link.raw_issues.append("NOFOLLOW_IN_NAV")
            self.issues.append(Issue(
                severity="critique",
                dimension="link_equity",
                code="NOFOLLOW_IN_NAV",
                message="Lien nofollow dans la navigation",
                detail=(
                    "Le nofollow dans le nav gaspille l'équité — elle s'évapore "
                    "au lieu d'être transmise. La solution est de retirer le lien."
                ),
                url=href,
            ))

    def handle_data(self, data: str) -> None:
        if self.in_a and self.current_link is not None:
            self.current_link.text += data.strip() + " "

    def handle_endtag(self, tag: str) -> None:
        if tag == "header":
            self.in_header = False
        if tag == "footer":
            self.in_footer = False

        if self.in_nav and self.current_nav is not None:
            if tag == "ul":
                self.ul_depth = max(0, self.ul_depth - 1)

            if tag == "a" and self.in_a and self.current_link is not None:
                self.in_a = False
                self.current_link.text = self.current_link.text.strip()

                if not self.current_link.text and not self.current_link.aria_label:
                    self.current_link.raw_issues.append("EMPTY_ANCHOR")
                    self.issues.append(Issue(
                        severity="critique",
                        dimension="anchor_text",
                        code="EMPTY_ANCHOR_TEXT",
                        message=f"Lien avec texte d'ancre vide : {self.current_link.href}",
                        detail="Pas de texte d'ancre ni d'aria-label — aucun signal contextuel.",
                        url=self.current_link.href,
                    ))

                self.current_nav.links.append(self.current_link)
                self.current_link = None

        if tag == "nav" and self.in_nav:
            self.nav_depth -= 1
            if self.nav_depth <= 0:
                self.in_nav = False
                self.nav_depth = 0
                self.ul_depth = 0
                if self.current_nav is not None:
                    self.navs.append(self.current_nav)
                self.current_nav = None

    def error(self, message: str) -> None:
        """Override default error behavior — best effort parsing."""
        self.malformed_detected = True
        print(f"[parse_nav] WARNING: HTML parse warning: {message}", file=sys.stderr)


def build_result(
    extractor: NavExtractor,
    page_label: str,
    source: str,
    html_length: int,
) -> dict:
    """Construit le dict final à sérialiser en JSON."""
    all_links: list[NavLink] = []
    for nav in extractor.navs:
        all_links.extend(nav.links)

    urls = [l.href for l in all_links if l.href and l.href != "#"]
    unique_urls = set(urls)
    url_counter = Counter(urls)
    duplicate_urls = {u: c for u, c in url_counter.items() if c > 1}
    top_level = [l for l in all_links if l.depth <= 1]

    if not extractor.navs:
        extractor.issues.append(Issue(
            severity="bloquant",
            dimension="semantic_html",
            code="NO_NAV_ELEMENT",
            message="Aucun élément <nav> trouvé dans le HTML",
            detail=(
                "Google ne peut pas identifier la zone de navigation principale. "
                "Screaming Frog ne peut pas classifier les liens par position."
            ),
        ))

    if not extractor.has_main:
        extractor.issues.append(Issue(
            severity="important",
            dimension="semantic_html",
            code="NO_MAIN_ELEMENT",
            message="Aucun élément <main> trouvé",
            detail="Sans <main>, Google a plus de difficulté à distinguer le contenu principal du boilerplate.",
        ))

    if extractor.malformed_detected:
        extractor.issues.append(Issue(
            severity="recommandation",
            dimension="parsing",
            code="MALFORMED_HTML",
            message="Le HTML contient des patterns malformés — parsing best-effort appliqué",
            detail="Le résultat est valide mais certains éléments ont pu être manqués.",
        ))

    issue_summary = {
        "bloquant": sum(1 for i in extractor.issues if i.severity == "bloquant"),
        "critique": sum(1 for i in extractor.issues if i.severity == "critique"),
        "important": sum(1 for i in extractor.issues if i.severity == "important"),
        "recommandation": sum(1 for i in extractor.issues if i.severity == "recommandation"),
    }

    return {
        "meta": {
            "extraction_date": datetime.now().isoformat(),
            "parser_version": PARSER_VERSION,
            "page_label": page_label,
            "source": source,
            "total_html_chars": html_length,
        },
        "semantic_structure": {
            "has_header": extractor.has_header,
            "has_nav": len(extractor.navs) > 0,
            "has_main": extractor.has_main,
            "has_footer": extractor.has_footer,
            "nav_count": len(extractor.navs),
            "semantic_elements_found": sorted(list(extractor.semantic_elements)),
        },
        "navs": [n.to_dict() for n in extractor.navs],
        "metrics": {
            "total_nav_links": len(all_links),
            "top_level_links": len(top_level),
            "unique_urls": len(unique_urls),
            "duplicate_urls_in_nav": duplicate_urls,
            "total_links_in_document": extractor.total_links_in_doc,
            "header_links": extractor.header_links,
            "footer_links": extractor.footer_links,
            "nav_to_total_ratio": round(
                len(all_links) / max(extractor.total_links_in_doc, 1) * 100, 1
            ),
        },
        "issues": [i.to_dict() for i in extractor.issues],
        "issue_summary": issue_summary,
        "all_nav_urls": sorted(list(unique_urls)),
        "all_nav_anchors": [
            {"text": l.text, "href": l.href, "depth": l.depth}
            for l in all_links
            if l.text
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse HTML navigation structure")
    parser.add_argument("--html", type=str, help="Path to HTML file")
    parser.add_argument("--stdin", action="store_true", help="Read HTML from stdin")
    parser.add_argument("--output", "-o", type=str, help="Output JSON file path")
    parser.add_argument("--label", type=str, default="Page", help="Page label")
    parser.add_argument("--pretty", action="store_true", default=True)

    args = parser.parse_args()

    try:
        if args.stdin:
            html_content = sys.stdin.read()
            source = "stdin"
        elif args.html:
            html_path = Path(args.html)
            if not html_path.exists():
                print(f"[parse_nav] ERROR: file not found: {html_path}", file=sys.stderr)
                return 1
            html_content = html_path.read_text(encoding="utf-8", errors="replace")
            source = str(html_path)
        else:
            print("[parse_nav] ERROR: provide --html <file> or --stdin", file=sys.stderr)
            return 1

        extractor = NavExtractor()
        malformed = False
        try:
            extractor.feed(html_content)
            extractor.close()
        except Exception as e:
            malformed = True
            extractor.malformed_detected = True
            print(f"[parse_nav] WARNING: HTML parse error, best-effort result: {e}", file=sys.stderr)

        result = build_result(extractor, args.label, source, len(html_content))
        json_str = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json_str, encoding="utf-8")
            print(f"[parse_nav] ✓ {out_path}", file=sys.stderr)
            s = result["issue_summary"]
            print(
                f"[parse_nav]   {s['bloquant']} bloquants | "
                f"{s['critique']} critiques | {s['important']} importants | "
                f"{s['recommandation']} recommandations",
                file=sys.stderr,
            )
            print(
                f"[parse_nav]   {result['metrics']['total_nav_links']} liens "
                f"dans {result['semantic_structure']['nav_count']} <nav>",
                file=sys.stderr,
            )
        else:
            print(json_str)

        return 2 if malformed else 0

    except Exception as e:
        print(f"[parse_nav] FATAL: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
