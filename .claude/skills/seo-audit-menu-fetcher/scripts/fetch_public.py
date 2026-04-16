#!/usr/bin/env python3
"""
fetch_public.py — Récupération d'URLs publiques via urllib (stdlib only).

Détecte automatiquement si la page est une SPA et le signale dans le JSON
de sortie pour que l'agent décide s'il faut aussi capturer le DOM rendu.

Usage :
    python3 fetch_public.py --url https://example.com --output-dir ./pages/ --label homepage

Exit codes :
    0 : succès complet
    1 : échec HTTP attendu (403, 404, etc.)
    2 : échec réseau (timeout, DNS, SSL)
    3 : erreur inattendue
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
import ssl
import socket
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


USER_AGENT = (
    "Mozilla/5.0 (compatible; seo-audit-for-claude-code/0.2; "
    "+https://github.com/agencekoeki/seo-audit-for-claude-code)"
)

SPA_PATTERNS = {
    "Next.js": [r"__NEXT_DATA__", r'id="__next"'],
    "Nuxt": [r"__NUXT__", r'id="__nuxt"', r"__NUXT_DATA__"],
    "React (generic)": [r"react-dom", r"_reactRootContainer", r"data-reactroot"],
    "Vue": [r"vue\.(min\.)?js", r"data-v-[a-f0-9]"],
    "Angular": [r"ng-version=", r"ng-app=", r"\[ng-"],
    "Svelte/SvelteKit": [r"__SVELTE__", r"svelte-[a-z0-9]"],
    "Gatsby": [r"___gatsby", r'id="___gatsby"'],
    "Remix": [r"__remixContext", r"__remixRouteModules"],
}


def detect_framework(html: str) -> str | None:
    """Détecte le framework JS utilisé, si applicable."""
    for name, patterns in SPA_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, html, re.IGNORECASE):
                return name
    return None


def fetch_url(url: str, timeout: int = 15) -> tuple[str, int, list[str]]:
    """Télécharge une URL. Retourne (html, status, warnings)."""
    warnings: list[str] = []
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                warnings.append(f"Content-Type '{content_type}' n'est pas HTML — parsing tentatif")
            raw = resp.read()
            encoding = resp.headers.get_content_charset() or "utf-8"
            try:
                html = raw.decode(encoding, errors="replace")
            except LookupError:
                html = raw.decode("utf-8", errors="replace")
                warnings.append(f"Encoding '{encoding}' inconnu — fallback utf-8")
            return html, status, warnings
    except HTTPError as e:
        raise
    except (URLError, socket.timeout, ssl.SSLError, ConnectionError) as e:
        raise


def build_result(
    success: bool,
    url: str,
    label: str,
    **kwargs,
) -> dict:
    result = {
        "success": success,
        "url": url,
        "label": label,
        "fetched_at": datetime.now().isoformat(),
    }
    result.update(kwargs)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch public URL for SEO audit")
    parser.add_argument("--url", required=True, help="URL to fetch")
    parser.add_argument("--output-dir", required=True, help="Directory where to save HTML")
    parser.add_argument("--label", default="page", help="Label for this page")
    parser.add_argument("--timeout", type=int, default=15, help="Timeout in seconds")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_file = output_dir / f"{args.label}-source.html"

    try:
        html, status, warnings = fetch_url(args.url, args.timeout)
    except HTTPError as e:
        result = build_result(
            success=False,
            url=args.url,
            label=args.label,
            http_status=e.code,
            reason=f"HTTP {e.code} {e.reason} — le serveur refuse la requête",
            suggestion="Si la page nécessite authentification, utiliser fetch_authenticated.py. Sinon vérifier que l'URL est correcte.",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    except socket.timeout:
        result = build_result(
            success=False,
            url=args.url,
            label=args.label,
            reason=f"Connection timeout ({args.timeout}s) — site indisponible ou très lent",
            suggestion="Augmenter le timeout avec --timeout, ou vérifier la connectivité réseau",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    except ssl.SSLError as e:
        result = build_result(
            success=False,
            url=args.url,
            label=args.label,
            reason=f"SSL certificate error : {e}",
            suggestion="Vérifier la configuration HTTPS du site (certificat expiré ?)",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    except URLError as e:
        result = build_result(
            success=False,
            url=args.url,
            label=args.label,
            reason=f"Erreur réseau : {e.reason}",
            suggestion="Vérifier l'URL, la connexion réseau, et les DNS",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    except Exception as e:
        result = build_result(
            success=False,
            url=args.url,
            label=args.label,
            reason=f"Erreur inattendue : {e}",
            trace=traceback.format_exc(),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3

    # Succès : écrire le fichier et analyser
    source_file.write_text(html, encoding="utf-8")
    framework = detect_framework(html)

    result = build_result(
        success=True,
        url=args.url,
        label=args.label,
        http_status=status,
        file_source=str(source_file),
        file_rendered=None,
        size_bytes=len(html.encode("utf-8")),
        is_spa=framework is not None,
        framework_detected=framework,
        warnings=warnings,
    )

    if framework:
        result["note"] = (
            f"Framework {framework} détecté. Pour un audit complet, "
            f"capturer aussi le DOM rendu via Playwright (scripts/capture_rendered.py)."
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[fetch_public] ✓ {args.label} ({len(html)} chars)", file=sys.stderr)
    if framework:
        print(f"[fetch_public]   Framework détecté : {framework}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
