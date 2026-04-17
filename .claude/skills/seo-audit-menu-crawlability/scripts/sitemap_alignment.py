#!/usr/bin/env python3
"""
sitemap_alignment.py — Croise les URLs du menu avec le sitemap.xml et robots.txt.

1. Parse robots.txt pour extraire les directives Sitemap et Disallow
2. Fetch chaque sitemap (gère les sitemap index récursifs)
3. Compare avec la liste des URLs du menu
4. Détecte : URLs du menu absentes du sitemap, URLs bloquées par robots.txt

Usage :
    python3 sitemap_alignment.py --site-url https://example.com --menu-urls menu_urls.json --output RESULTS.json [--insecure]

Input (menu_urls.json) : ["https://example.com/foo", "https://example.com/bar", ...]

Codes de sortie :
    0 : succès
    1 : erreur d'entrée
    2 : erreur réseau
    3 : erreur inattendue
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree


USER_AGENT = (
    "Mozilla/5.0 (compatible; seo-audit-for-claude-code/0.3; "
    "+https://github.com/agencekoeki/seo-audit-for-claude-code)"
)


def fetch_text(url: str, timeout: int = 15, insecure: bool = False) -> str | None:
    """Fetch une URL et retourne le texte, ou None si erreur."""
    ctx = None
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        print(f"[sitemap_alignment]   ⚠ Impossible de fetcher {url} : {e}", file=sys.stderr)
        return None


def parse_robots_txt(text: str) -> dict:
    """Parse robots.txt, retourne {sitemaps: [...], disallow_rules: [...]}."""
    sitemaps: list[str] = []
    disallow_rules: list[str] = []
    current_agent = "*"

    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        if line.lower().startswith("sitemap:"):
            sitemaps.append(line.split(":", 1)[1].strip())
        elif line.lower().startswith("user-agent:"):
            current_agent = line.split(":", 1)[1].strip()
        elif line.lower().startswith("disallow:") and current_agent in ("*", "Googlebot"):
            path = line.split(":", 1)[1].strip()
            if path:
                disallow_rules.append(path)

    return {"sitemaps": sitemaps, "disallow_rules": disallow_rules}


def is_disallowed(url: str, rules: list[str]) -> bool:
    """Vérifie si une URL est bloquée par une règle Disallow."""
    parsed = urlparse(url)
    path = parsed.path
    for rule in rules:
        if rule.endswith("*"):
            if path.startswith(rule[:-1]):
                return True
        elif path.startswith(rule):
            return True
    return False


def parse_sitemap(text: str) -> tuple[list[str], list[str]]:
    """Parse un sitemap XML. Retourne (urls, sub_sitemaps)."""
    urls: list[str] = []
    sub_sitemaps: list[str] = []

    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return urls, sub_sitemaps

    # Namespace handling (sitemaps utilisent souvent le ns par défaut)
    ns = ""
    match = re.match(r"\{(.+?)\}", root.tag)
    if match:
        ns = match.group(1)

    def tag(name: str) -> str:
        return f"{{{ns}}}{name}" if ns else name

    # Sitemap index
    for sitemap_el in root.findall(tag("sitemap")):
        loc = sitemap_el.find(tag("loc"))
        if loc is not None and loc.text:
            sub_sitemaps.append(loc.text.strip())

    # URL set
    for url_el in root.findall(tag("url")):
        loc = url_el.find(tag("loc"))
        if loc is not None and loc.text:
            urls.append(loc.text.strip())

    return urls, sub_sitemaps


def collect_sitemap_urls(
    sitemap_urls: list[str], insecure: bool = False, max_depth: int = 3
) -> tuple[list[str], list[str]]:
    """Fetch récursivement les sitemaps et collecte toutes les URLs.

    Retourne (urls_collectées, erreurs_fetch).
    """
    all_urls: list[str] = []
    fetch_errors: list[str] = []
    visited: set[str] = set()
    queue = [(u, 0) for u in sitemap_urls]

    while queue:
        sm_url, depth = queue.pop(0)
        if sm_url in visited or depth > max_depth:
            continue
        visited.add(sm_url)

        print(f"[sitemap_alignment]   Lecture sitemap : {sm_url}", file=sys.stderr)
        text = fetch_text(sm_url, insecure=insecure)
        if not text:
            fetch_errors.append(sm_url)
            continue

        urls, subs = parse_sitemap(text)
        all_urls.extend(urls)
        for sub in subs:
            queue.append((sub, depth + 1))

    return all_urls, fetch_errors


def normalize_url(url: str) -> str:
    """Normalise une URL pour comparaison (lowercase host, trailing slash)."""
    parsed = urlparse(url.lower())
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Croisement URLs menu vs sitemap vs robots.txt")
    parser.add_argument("--site-url", required=True, help="URL racine du site (ex: https://example.com)")
    parser.add_argument("--menu-urls", required=True, help="Fichier JSON avec la liste des URLs du menu")
    parser.add_argument("--output", required=True, help="Fichier JSON de sortie")
    parser.add_argument("--insecure", action="store_true", help="Ignorer les erreurs SSL")

    args = parser.parse_args()

    # Lire les URLs du menu
    try:
        with open(args.menu_urls, "r", encoding="utf-8") as f:
            menu_urls = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[sitemap_alignment] ✗ Erreur lecture {args.menu_urls} : {e}", file=sys.stderr)
        return 1

    if not isinstance(menu_urls, list):
        print("[sitemap_alignment] ✗ Le fichier doit contenir un tableau JSON d'URLs", file=sys.stderr)
        return 1

    site = args.site_url.rstrip("/")
    print(f"[sitemap_alignment] Analyse pour {site} ({len(menu_urls)} URLs menu)...", file=sys.stderr)

    # 1. Fetch robots.txt
    robots_url = f"{site}/robots.txt"
    print(f"[sitemap_alignment] Lecture robots.txt : {robots_url}", file=sys.stderr)
    robots_text = fetch_text(robots_url, insecure=args.insecure)
    robots = parse_robots_txt(robots_text) if robots_text else {"sitemaps": [], "disallow_rules": []}

    # 2. Sitemap : soit depuis robots.txt, soit fallback /sitemap.xml
    sitemap_sources = robots["sitemaps"] if robots["sitemaps"] else [f"{site}/sitemap.xml"]
    sitemap_urls, sitemap_errors = collect_sitemap_urls(sitemap_sources, insecure=args.insecure)
    sitemap_reachable = len(sitemap_errors) == 0 or len(sitemap_urls) > 0
    print(f"[sitemap_alignment]   {len(sitemap_urls)} URLs dans le sitemap", file=sys.stderr)
    if sitemap_errors:
        print(f"[sitemap_alignment]   ⚠ {len(sitemap_errors)} sitemap(s) non lisible(s)", file=sys.stderr)

    # 3. Normaliser pour comparaison
    sitemap_set = {normalize_url(u) for u in sitemap_urls}

    # 4. Croiser — SEULEMENT si le sitemap a été lu avec succès
    menu_not_in_sitemap: list[str] = []
    menu_disallowed: list[dict] = []
    menu_in_sitemap: list[str] = []

    if sitemap_reachable:
        for url in menu_urls:
            norm = normalize_url(url)
            in_sitemap = norm in sitemap_set
            disallowed = is_disallowed(url, robots["disallow_rules"])

            if disallowed:
                menu_disallowed.append({"url": url, "matching_rule": next((r for r in robots["disallow_rules"] if url.startswith(site + r.rstrip("*"))), None)})
            elif not in_sitemap:
                menu_not_in_sitemap.append(url)
            else:
                menu_in_sitemap.append(url)

    result = {
        "site_url": site,
        "robots_txt_found": robots_text is not None,
        "robots_disallow_rules": robots["disallow_rules"],
        "sitemap_sources": sitemap_sources,
        "sitemap_total_urls": len(sitemap_urls),
        "sitemap_reachable": sitemap_reachable,
        "sitemap_fetch_errors": sitemap_errors,
        "menu_urls_total": len(menu_urls),
        "menu_in_sitemap": len(menu_in_sitemap),
        "menu_not_in_sitemap": menu_not_in_sitemap,
        "menu_disallowed_by_robots": menu_disallowed,
        "issues": [],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    # Issue : sitemap non lisible → JE NE PEUX PAS VÉRIFIER
    if not sitemap_reachable:
        result["issues"].append({
            "test": "sitemap_unreachable",
            "checklist_id": "1.4.1",
            "severity": None,
            "classification": "cannot_verify",
            "detail": f"Le(s) sitemap(s) {', '.join(sitemap_errors)} n'ont pas pu être lus. "
                      f"Impossible de vérifier si les URLs du menu y sont présentes.",
        })

    if menu_disallowed:
        result["issues"].append({
            "test": "menu_urls_robots_blocked",
            "checklist_id": "1.4.2",
            "severity": "BLOQUANT",
            "count": len(menu_disallowed),
            "urls": [m["url"] for m in menu_disallowed],
        })

    if menu_not_in_sitemap:
        result["issues"].append({
            "test": "menu_urls_missing_from_sitemap",
            "checklist_id": "1.4.1",
            "severity": "IMPORTANT",
            "count": len(menu_not_in_sitemap),
            "urls": menu_not_in_sitemap,
        })

    # Écrire
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"[sitemap_alignment] ✓ {len(menu_in_sitemap)} OK, "
        f"{len(menu_not_in_sitemap)} absentes du sitemap, "
        f"{len(menu_disallowed)} bloquées robots.txt",
        file=sys.stderr,
    )
    print(json.dumps({
        "in_sitemap": len(menu_in_sitemap),
        "missing": len(menu_not_in_sitemap),
        "blocked": len(menu_disallowed),
        "output_file": args.output,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[sitemap_alignment] ✗ Erreur inattendue : {e}", file=sys.stderr)
        sys.exit(3)
