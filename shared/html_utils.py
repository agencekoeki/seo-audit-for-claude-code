"""
html_utils.py — Utilitaires HTML partagés entre scripts d'audit.

Fonctions stdlib-only (pas de BeautifulSoup) pour des tâches courantes :
- Détection de framework JS
- Normalisation d'URLs
- Comptage d'éléments
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse


SPA_PATTERNS: dict[str, list[str]] = {
    "Next.js": [r"__NEXT_DATA__", r'id="__next"'],
    "Nuxt": [r"__NUXT__", r'id="__nuxt"', r"__NUXT_DATA__"],
    "React": [r"react-dom", r"_reactRootContainer", r"data-reactroot"],
    "Vue": [r"vue\.(min\.)?js", r"data-v-[a-f0-9]"],
    "Angular": [r"ng-version=", r"ng-app=", r"\[ng-"],
    "Svelte/SvelteKit": [r"__SVELTE__", r"svelte-[a-z0-9]"],
    "Gatsby": [r"___gatsby", r'id="___gatsby"'],
    "Remix": [r"__remixContext", r"__remixRouteModules"],
}


def detect_framework(html: str) -> str | None:
    """Retourne le nom du framework JS détecté, ou None."""
    for name, patterns in SPA_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, html, re.IGNORECASE):
                return name
    return None


def normalize_url(url: str, base: str | None = None) -> str:
    """
    Normalise une URL pour comparaison.

    - Supprime le fragment (#)
    - Résout les chemins relatifs si base fourni
    - Normalise trailing slash
    """
    if not url:
        return ""

    parsed = urlparse(url)
    # Supprime le fragment
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip("/") or "/",
        parsed.params,
        parsed.query,
        "",  # pas de fragment
    ))

    if not parsed.scheme and base:
        base_parsed = urlparse(base)
        if url.startswith("/"):
            return urlunparse((
                base_parsed.scheme,
                base_parsed.netloc,
                url.rstrip("/") or "/",
                "",
                "",
                "",
            ))

    return normalized


def count_elements(html: str, tag: str) -> int:
    """Compte les occurrences d'un tag HTML (approximatif, regex-based)."""
    pattern = rf"<{tag}\b"
    return len(re.findall(pattern, html, re.IGNORECASE))


def has_element(html: str, tag: str) -> bool:
    """Détecte la présence d'un tag HTML."""
    return bool(re.search(rf"<{tag}\b", html, re.IGNORECASE))


def extract_meta_content(html: str, name: str) -> str | None:
    """Extrait le contenu d'un <meta name="..."> ou <meta property="...">"""
    match = re.search(
        rf'<meta\s+(?:name|property)=["\']{re.escape(name)}["\']\s+content=["\']([^"\']*)["\']',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    match = re.search(
        rf'<meta\s+content=["\']([^"\']*)["\']\s+(?:name|property)=["\']{re.escape(name)}["\']',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return None
