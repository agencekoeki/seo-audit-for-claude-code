#!/usr/bin/env python3
"""
diff_source_vs_rendered.py — Diff entre HTML source et DOM rendu.

Identifie les liens de navigation présents dans le rendu mais absents du source.
Ces liens sont invisibles à Googlebot en première passe — risque de non-indexation.

Usage :
    python3 diff_source_vs_rendered.py \
        --source page-source.html \
        --rendered page-rendered.html \
        --output diff.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from dataclasses import dataclass, field


SPA_PATTERNS = {
    "Next.js": [r"__NEXT_DATA__"],
    "Nuxt": [r"__NUXT__"],
    "React": [r"react-dom", r"_reactRootContainer"],
    "Vue": [r"data-v-[a-f0-9]"],
    "Angular": [r"ng-version="],
    "Svelte": [r"__SVELTE__"],
    "Gatsby": [r"___gatsby"],
    "Remix": [r"__remixContext"],
}


@dataclass
class LinkExtract:
    """Lien extrait d'un HTML."""
    href: str
    text: str
    in_nav: bool


class SimpleLinkExtractor(HTMLParser):
    """Extracteur léger de liens, avec flag si dans <nav>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[LinkExtract] = []
        self.nav_depth = 0
        self.current_link: LinkExtract | None = None
        self.in_a = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attrs_dict = {k: (v or "") for k, v in attrs}
        if tag == "nav":
            self.nav_depth += 1
        if tag == "a":
            self.in_a = True
            self.current_link = LinkExtract(
                href=attrs_dict.get("href", ""),
                text="",
                in_nav=self.nav_depth > 0,
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav" and self.nav_depth > 0:
            self.nav_depth -= 1
        if tag == "a" and self.in_a and self.current_link is not None:
            self.current_link.text = self.current_link.text.strip()
            self.links.append(self.current_link)
            self.current_link = None
            self.in_a = False

    def handle_data(self, data: str) -> None:
        if self.in_a and self.current_link is not None:
            self.current_link.text += data.strip() + " "


def extract_links(html: str) -> tuple[list[LinkExtract], bool]:
    """Extrait les liens. Retourne (links, malformed)."""
    extractor = SimpleLinkExtractor()
    malformed = False
    try:
        extractor.feed(html)
        extractor.close()
    except Exception:
        malformed = True
    return extractor.links, malformed


def detect_framework(html: str) -> str | None:
    for name, patterns in SPA_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, html, re.IGNORECASE):
                return name
    return None


def has_nav_element(html: str) -> bool:
    return bool(re.search(r"<nav\b", html, re.IGNORECASE))


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff source vs rendered HTML")
    parser.add_argument("--source", required=True, help="HTML source file (pre-JS)")
    parser.add_argument("--rendered", required=True, help="HTML rendered file (post-JS)")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()

    src_path = Path(args.source)
    rnd_path = Path(args.rendered)

    if not src_path.exists():
        print(f"[diff] ERROR: source file not found: {src_path}", file=sys.stderr)
        return 1
    if not rnd_path.exists():
        print(f"[diff] ERROR: rendered file not found: {rnd_path}", file=sys.stderr)
        return 1

    source_html = src_path.read_text(encoding="utf-8", errors="replace")
    rendered_html = rnd_path.read_text(encoding="utf-8", errors="replace")

    src_links, src_malformed = extract_links(source_html)
    rnd_links, rnd_malformed = extract_links(rendered_html)

    src_nav_links = [l for l in src_links if l.in_nav]
    rnd_nav_links = [l for l in rnd_links if l.in_nav]

    src_nav_urls = {l.href for l in src_nav_links if l.href and l.href != "#"}
    rnd_nav_urls = {l.href for l in rnd_nav_links if l.href and l.href != "#"}

    # Diff
    urls_only_in_rendered = rnd_nav_urls - src_nav_urls  # invisibles au crawl 1ère passe
    urls_only_in_source = src_nav_urls - rnd_nav_urls  # présents source mais pas rendered (étrange)
    urls_in_both = src_nav_urls & rnd_nav_urls

    src_framework = detect_framework(source_html)
    rnd_framework = detect_framework(rendered_html)

    src_has_nav = has_nav_element(source_html)
    rnd_has_nav = has_nav_element(rendered_html)

    issues = []

    if not src_has_nav and rnd_has_nav:
        issues.append({
            "severity": "bloquant",
            "dimension": "crawlability",
            "code": "NAV_MISSING_IN_SOURCE",
            "message": "L'élément <nav> n'existe PAS dans le HTML source (pré-JS)",
            "detail": (
                "Le menu est créé entièrement par JavaScript. Googlebot en première passe "
                "ne voit aucun menu. Ce n'est récupéré qu'en seconde passe (rendering), "
                "qui est différé et limité en budget."
            ),
            "evidence": f"source: nav={src_has_nav}, rendered: nav={rnd_has_nav}",
        })

    if urls_only_in_rendered:
        issues.append({
            "severity": "bloquant" if len(urls_only_in_rendered) > 5 else "critique",
            "dimension": "crawlability",
            "code": "LINKS_ONLY_IN_RENDERED_DOM",
            "message": f"{len(urls_only_in_rendered)} URL(s) de navigation présente(s) uniquement dans le DOM rendu",
            "detail": (
                "Ces URLs sont créées par JavaScript et invisibles au crawl en première passe. "
                "Risque élevé de non-indexation ou d'indexation tardive. "
                "Solution : SSR (Server-Side Rendering) ou prerendering."
            ),
            "evidence": sorted(list(urls_only_in_rendered))[:10],
        })

    if urls_only_in_source:
        issues.append({
            "severity": "important",
            "dimension": "crawlability",
            "code": "LINKS_ONLY_IN_SOURCE",
            "message": f"{len(urls_only_in_source)} URL(s) dans source mais PAS dans rendered",
            "detail": (
                "Ces URLs existent en HTML source mais disparaissent après JS. "
                "Peut indiquer un bug d'hydratation ou un menu remplacé côté client. "
                "À investiguer."
            ),
            "evidence": sorted(list(urls_only_in_source))[:10],
        })

    if rnd_framework and not src_has_nav:
        issues.append({
            "severity": "important",
            "dimension": "crawlability",
            "code": "CSR_ONLY_FRAMEWORK",
            "message": f"Framework {rnd_framework} détecté sans SSR apparent",
            "detail": (
                f"Le framework {rnd_framework} supporte le SSR mais ce site semble "
                f"utiliser uniquement le Client-Side Rendering. "
                f"Activer le SSR (Next.js: getServerSideProps/getStaticProps, "
                f"Nuxt: server routes) pour que Googlebot voie le menu en première passe."
            ),
        })

    result = {
        "meta": {
            "analyzed_at": datetime.now().isoformat(),
            "source_file": str(src_path),
            "rendered_file": str(rnd_path),
            "source_size_bytes": len(source_html.encode("utf-8")),
            "rendered_size_bytes": len(rendered_html.encode("utf-8")),
        },
        "frameworks": {
            "source": src_framework,
            "rendered": rnd_framework,
        },
        "semantic": {
            "source_has_nav": src_has_nav,
            "rendered_has_nav": rnd_has_nav,
        },
        "link_counts": {
            "source_total_links": len(src_links),
            "rendered_total_links": len(rnd_links),
            "source_nav_links": len(src_nav_links),
            "rendered_nav_links": len(rnd_nav_links),
        },
        "url_sets": {
            "source_nav_unique": len(src_nav_urls),
            "rendered_nav_unique": len(rnd_nav_urls),
            "in_both": len(urls_in_both),
            "only_in_rendered": sorted(list(urls_only_in_rendered)),
            "only_in_source": sorted(list(urls_only_in_source)),
        },
        "issues": issues,
        "verdict": (
            "BLOQUANT"
            if any(i["severity"] == "bloquant" for i in issues)
            else "CRITIQUE"
            if any(i["severity"] == "critique" for i in issues)
            else "OK"
        ),
        "warnings": {
            "source_malformed": src_malformed,
            "rendered_malformed": rnd_malformed,
        },
    }

    json_str = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_str, encoding="utf-8")
        print(f"[diff] ✓ {out}", file=sys.stderr)
        print(
            f"[diff]   source={len(src_nav_urls)} URLs nav | "
            f"rendered={len(rnd_nav_urls)} URLs nav | "
            f"only_rendered={len(urls_only_in_rendered)}",
            file=sys.stderr,
        )
    else:
        print(json_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
