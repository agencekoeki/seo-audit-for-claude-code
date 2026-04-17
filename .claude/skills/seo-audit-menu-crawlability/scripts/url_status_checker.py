#!/usr/bin/env python3
"""
url_status_checker.py — Vérifie le statut HTTP d'une liste d'URLs.

Fait un GET partiel (8 Ko max) sur chaque URL pour récupérer :
- La chaîne de redirections (max 5 sauts)
- Le statut HTTP final
- Le Content-Type
- Les directives meta robots et X-Robots-Tag
- Le temps de réponse

Parallélisé via concurrent.futures.ThreadPoolExecutor (max 8 workers).
Python 3.10+ stdlib uniquement — pas de requests, pas de httpx.

Usage :
    python3 url_status_checker.py --input urls.json --output statuses.json [--timeout 10] [--insecure] [--cookies-from-playwright-profile PATH]

Input format (urls.json) :
    [
        {"url": "https://example.com/foo", "context": "breadcrumb fiche_praticien"},
        {"url": "https://example.com/bar", "context": "menu principal"}
    ]

Output format (statuses.json) — un tableau JSON avec un objet par URL.

Codes de sortie :
    0 : succès (toutes les URLs vérifiées, même si certaines sont en erreur)
    1 : erreur d'entrée (fichier manquant, JSON invalide)
    3 : erreur inattendue
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import ssl
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.client import HTTPResponse
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, HTTPSHandler, HTTPCookieProcessor
from http.cookiejar import MozillaCookieJar, Cookie


USER_AGENT = (
    "Mozilla/5.0 (compatible; seo-audit-for-claude-code/0.3; "
    "+https://github.com/agencekoeki/seo-audit-for-claude-code)"
)

# Volume max de body à lire pour extraire meta robots (8 Ko)
MAX_BODY_READ = 8192


class NoRedirectHandler(HTTPRedirectHandler):
    """Handler qui capture les redirections au lieu de les suivre automatiquement."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Ne pas suivre, on gère manuellement


def load_cookies_from_playwright_profile(profile_dir: str) -> str | None:
    """Lit les cookies depuis le SQLite d'un profil Playwright Chromium.

    Retourne le header Cookie formaté, ou None si impossible.
    Le fichier est copié dans un tempdir pour éviter le lock si Chromium tourne.
    """
    profile_path = Path(profile_dir)

    # Chromium stocke les cookies dans Default/Cookies ou directement Cookies
    candidates = [
        profile_path / "Default" / "Cookies",
        profile_path / "Cookies",
    ]
    cookies_db = None
    for c in candidates:
        if c.exists():
            cookies_db = c
            break

    if not cookies_db:
        print(f"[url_status_checker] ⚠ Fichier Cookies introuvable dans {profile_dir}", file=sys.stderr)
        return None

    # Copier pour éviter le lock SQLite si Chromium tourne encore
    tmp_dir = tempfile.mkdtemp(prefix="seo-audit-cookies-")
    tmp_db = Path(tmp_dir) / "Cookies"
    try:
        shutil.copy2(cookies_db, tmp_db)
    except (PermissionError, OSError) as e:
        print(f"[url_status_checker] ⚠ Impossible de copier {cookies_db} : {e}", file=sys.stderr)
        return None

    cookies: list[tuple[str, str, str, str]] = []  # (host, name, value, path)
    try:
        conn = sqlite3.connect(str(tmp_db))
        cursor = conn.execute(
            "SELECT host_key, name, value, path FROM cookies WHERE value != ''"
        )
        for host_key, name, value, path in cursor:
            cookies.append((host_key, name, value, path))
        conn.close()
    except sqlite3.Error as e:
        print(f"[url_status_checker] ⚠ Erreur lecture SQLite cookies : {e}", file=sys.stderr)
        return None
    finally:
        # Nettoyer le fichier temporaire
        try:
            tmp_db.unlink()
            Path(tmp_dir).rmdir()
        except OSError:
            pass

    if not cookies:
        print(f"[url_status_checker] ⚠ Aucun cookie trouvé dans le profil Playwright", file=sys.stderr)
        return None

    print(f"[url_status_checker] ✓ {len(cookies)} cookies chargés depuis le profil Playwright", file=sys.stderr)
    return cookies


def format_cookie_header(cookies: list[tuple[str, str, str, str]], url: str) -> str:
    """Formate les cookies pertinents pour une URL en header Cookie."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    url_path = parsed.path or "/"

    matching = []
    for host_key, name, value, cookie_path in cookies:
        # Matcher le domaine (avec le . prefix pour les cookies de domaine)
        if hostname == host_key or hostname.endswith(host_key):
            # Matcher le path
            if url_path.startswith(cookie_path):
                matching.append(f"{name}={value}")

    return "; ".join(matching)


def create_opener(insecure: bool = False):
    """Crée un opener urllib avec gestion SSL optionnelle."""
    handlers = [NoRedirectHandler]
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(HTTPSHandler(context=ctx))
    return build_opener(*handlers)


def extract_meta_robots(html_bytes: bytes) -> str | None:
    """Extrait le contenu de <meta name='robots'> depuis un fragment HTML."""
    try:
        text = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        return None
    match = re.search(
        r'<meta\s[^>]*name\s*=\s*["\']robots["\'][^>]*content\s*=\s*["\']([^"\']+)["\']',
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    # Ordre inversé des attributs (content avant name)
    match = re.search(
        r'<meta\s[^>]*content\s*=\s*["\']([^"\']+)["\'][^>]*name\s*=\s*["\']robots["\']',
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return None


def check_single_url(
    url: str,
    context: str,
    opener,
    timeout: int,
    max_redirects: int = 5,
    cookies: list[tuple[str, str, str, str]] | None = None,
) -> dict[str, Any]:
    """Vérifie une URL : suit les redirections, extrait meta robots."""
    start = time.monotonic()
    status_codes: list[int] = []
    redirect_chain: list[str] = [url]
    current_url = url
    final_status = None
    content_type = None
    x_robots_tag = None
    meta_robots = None
    error_msg = None

    for _ in range(max_redirects + 1):
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,*/*"}
        # Ajouter les cookies si disponibles
        if cookies:
            cookie_header = format_cookie_header(cookies, current_url)
            if cookie_header:
                headers["Cookie"] = cookie_header
        req = Request(
            current_url,
            method="GET",
            headers=headers,
        )
        try:
            resp = opener.open(req, timeout=timeout)
            status_codes.append(resp.status)
            final_status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            x_robots_tag = resp.headers.get("X-Robots-Tag")

            # Lire un fragment pour extraire meta robots si c'est du HTML
            if "text/html" in content_type or "application/xhtml" in content_type:
                body_fragment = resp.read(MAX_BODY_READ)
                meta_robots = extract_meta_robots(body_fragment)
            resp.close()
            break  # Pas de redirection, on sort

        except HTTPError as e:
            status_codes.append(e.code)
            final_status = e.code

            # Gérer les redirections (301, 302, 303, 307, 308)
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get("Location")
                if not location:
                    error_msg = f"HTTP {e.code} sans header Location"
                    break
                # Résoudre les URLs relatives
                if location.startswith("/"):
                    parsed = urlparse(current_url)
                    location = f"{parsed.scheme}://{parsed.netloc}{location}"
                redirect_chain.append(location)
                current_url = location
                # Extraire X-Robots-Tag de la réponse de redirection
                x_robots_redir = e.headers.get("X-Robots-Tag")
                if x_robots_redir and not x_robots_tag:
                    x_robots_tag = x_robots_redir
                continue
            else:
                content_type = e.headers.get("Content-Type", "")
                x_robots_tag = e.headers.get("X-Robots-Tag")
                # Tenter d'extraire meta robots même sur les erreurs
                try:
                    body_fragment = e.read(MAX_BODY_READ)
                    if "text/html" in content_type:
                        meta_robots = extract_meta_robots(body_fragment)
                except Exception:
                    pass
                break

        except (URLError, TimeoutError, OSError) as e:
            error_msg = str(getattr(e, "reason", e))
            break

        except Exception as e:
            error_msg = f"Erreur inattendue : {e}"
            break

    elapsed_ms = round((time.monotonic() - start) * 1000)

    return {
        "url": url,
        "context": context,
        "final_url": redirect_chain[-1],
        "status_codes": status_codes,
        "redirect_chain_length": len(redirect_chain) - 1,
        "redirect_chain": redirect_chain if len(redirect_chain) > 1 else None,
        "final_status": final_status,
        "content_type": content_type,
        "x_robots_tag": x_robots_tag,
        "meta_robots": meta_robots,
        "response_time_ms": elapsed_ms,
        "error": error_msg,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vérifie le statut HTTP d'une liste d'URLs pour audit SEO"
    )
    parser.add_argument("--input", required=True, help="Fichier JSON d'entrée (liste d'URLs)")
    parser.add_argument("--output", required=True, help="Fichier JSON de sortie (statuts)")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout par requête en secondes")
    parser.add_argument("--insecure", action="store_true", help="Ignorer les erreurs SSL (domaines dev)")
    parser.add_argument("--workers", type=int, default=8, help="Nombre de workers parallèles")
    parser.add_argument("--cookies-from-playwright-profile", dest="cookies_profile",
                        help="Chemin du profil Playwright pour extraire les cookies OAuth")

    args = parser.parse_args()

    # Charger les cookies si profil spécifié
    cookies = None
    if args.cookies_profile:
        cookies = load_cookies_from_playwright_profile(args.cookies_profile)
        if not cookies:
            print("[url_status_checker] ⚠ Pas de cookies chargés — les requêtes auth risquent d'échouer", file=sys.stderr)

    # Lire le fichier d'entrée
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            urls_data = json.load(f)
    except FileNotFoundError:
        print(f"[url_status_checker] ✗ Fichier introuvable : {args.input}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"[url_status_checker] ✗ JSON invalide dans {args.input} : {e}", file=sys.stderr)
        return 1

    if not isinstance(urls_data, list) or len(urls_data) == 0:
        print("[url_status_checker] ✗ Le fichier d'entrée doit être un tableau JSON non vide", file=sys.stderr)
        return 1

    print(f"[url_status_checker] Vérification de {len(urls_data)} URLs (timeout={args.timeout}s, workers={args.workers})...", file=sys.stderr)

    opener = create_opener(insecure=args.insecure)
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for item in urls_data:
            url = item.get("url", "") if isinstance(item, dict) else str(item)
            context = item.get("context", "") if isinstance(item, dict) else ""
            if not url:
                continue
            future = pool.submit(check_single_url, url, context, opener, args.timeout, cookies=cookies)
            futures[future] = url

        for future in as_completed(futures):
            url = futures[future]
            try:
                result = future.result()
                results.append(result)
                status_str = str(result["final_status"]) if result["final_status"] else "ERR"
                chain_str = f" ({result['redirect_chain_length']} redirects)" if result["redirect_chain_length"] > 0 else ""
                print(f"[url_status_checker]   {status_str}{chain_str} {url}", file=sys.stderr)
            except Exception as e:
                results.append({
                    "url": url,
                    "context": futures[future],
                    "error": f"Exception worker : {e}",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                })

    # Trier par URL pour un output déterministe
    results.sort(key=lambda r: r.get("url", ""))

    # Écrire le fichier de sortie
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Résumé
    total = len(results)
    ok = sum(1 for r in results if r.get("final_status") == 200)
    redirects = sum(1 for r in results if r.get("redirect_chain_length", 0) > 0)
    errors_4xx = sum(1 for r in results if r.get("final_status") and 400 <= r["final_status"] < 500)
    errors_5xx = sum(1 for r in results if r.get("final_status") and r["final_status"] >= 500)
    network_err = sum(1 for r in results if r.get("error") and not r.get("final_status"))

    print(
        f"[url_status_checker] ✓ {total} URLs vérifiées → "
        f"{ok} OK, {redirects} redirects, {errors_4xx} 4xx, {errors_5xx} 5xx, {network_err} erreurs réseau",
        file=sys.stderr,
    )

    # JSON résumé sur stdout (pour consommation par les agents)
    summary = {
        "total": total,
        "ok_200": ok,
        "redirects": redirects,
        "errors_4xx": errors_4xx,
        "errors_5xx": errors_5xx,
        "network_errors": network_err,
        "output_file": args.output,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[url_status_checker] ✗ Erreur inattendue : {e}", file=sys.stderr)
        sys.exit(3)
