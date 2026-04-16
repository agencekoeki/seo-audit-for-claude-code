#!/usr/bin/env python3
"""
fetch_authenticated.py — Récupération d'URLs protégées.

Ce script NE lance PAS Playwright lui-même. C'est l'agent qui doit appeler
les outils Playwright MCP (browser_navigate, browser_snapshot, etc.).

Ce script sert à :
1. Valider que Playwright MCP est disponible
2. Générer le protocole que l'agent doit suivre
3. Sauvegarder les outputs fournis par l'agent dans le bon format

Le rôle de ce script est d'imposer une structure de sortie cohérente avec
les autres fetchers, pour que les agents d'analyse en aval aient toujours
les mêmes fichiers au même endroit.

Usage (mode 1 — générer le protocole) :
    python3 fetch_authenticated.py --url URL --output-dir DIR --label LABEL --emit-protocol

Usage (mode 2 — sauvegarder les outputs Playwright) :
    python3 fetch_authenticated.py --url URL --output-dir DIR --label LABEL \
      --save-source source.html --save-rendered rendered.html
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


SPA_PATTERNS = {
    "Next.js": [r"__NEXT_DATA__"],
    "Nuxt": [r"__NUXT__"],
    "React": [r"react-dom", r"_reactRootContainer"],
    "Vue": [r"data-v-[a-f0-9]"],
    "Angular": [r"ng-version="],
    "Svelte": [r"__SVELTE__"],
    "Gatsby": [r"___gatsby"],
}


def detect_framework(html: str) -> str | None:
    for name, patterns in SPA_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, html, re.IGNORECASE):
                return name
    return None


def emit_protocol(url: str, output_dir: str, label: str) -> int:
    """Imprime le protocole que l'agent doit suivre avec Playwright MCP."""
    protocol = {
        "action": "playwright_workflow",
        "url": url,
        "output_dir": output_dir,
        "label": label,
        "steps": [
            {
                "step": 1,
                "tool": "browser_navigate",
                "args": {"url": url},
                "description": "Naviguer vers l'URL. Une fenêtre Chrome visible va s'ouvrir.",
            },
            {
                "step": 2,
                "tool": "manual_action",
                "description": (
                    "DEMANDER À L'UTILISATEUR de se connecter manuellement dans "
                    "la fenêtre Chrome. Attendre son signal (ex: 'je suis connecté' "
                    "ou 'ok connecté')."
                ),
            },
            {
                "step": 3,
                "tool": "browser_navigate",
                "args": {"url": url},
                "description": (
                    "Re-naviguer vers l'URL cible après login (au cas où login "
                    "a redirigé ailleurs)."
                ),
            },
            {
                "step": 4,
                "tool": "browser_wait_for",
                "args": {"text": "", "time": 3},
                "description": "Attendre 3 secondes pour laisser le JS finir son rendu.",
            },
            {
                "step": 5,
                "tool": "browser_evaluate",
                "args": {"function": "() => document.documentElement.outerHTML"},
                "description": (
                    "Récupérer le HTML rendu (après exécution JS). "
                    f"Sauvegarder dans : {output_dir}/{label}-rendered.html"
                ),
            },
            {
                "step": 6,
                "tool": "browser_take_screenshot",
                "args": {
                    "filename": f"{output_dir}/{label}-screenshot.png",
                    "fullPage": False,
                },
                "description": "Capture d'écran pour référence visuelle.",
            },
            {
                "step": 7,
                "tool": "fetch_public_equivalent",
                "description": (
                    "Pour le HTML source (pré-JS), tenter un fetch public avec "
                    "les cookies de session. Si impossible, documenter la limite "
                    "dans le rapport : 'HTML source non disponible pour ce site "
                    "authentifié'."
                ),
            },
            {
                "step": 8,
                "tool": "save_via_this_script",
                "description": (
                    "Rappeler ce script avec les flags --save-source et "
                    "--save-rendered pour générer le JSON de résultat final."
                ),
            },
        ],
        "expected_outputs": [
            f"{output_dir}/{label}-source.html (optionnel, si accessible)",
            f"{output_dir}/{label}-rendered.html (obligatoire)",
            f"{output_dir}/{label}-screenshot.png (recommandé)",
        ],
        "fallback": (
            "Si Playwright MCP n'est pas disponible, demander à l'utilisateur de "
            "copier-coller manuellement le HTML depuis son navigateur connecté "
            "(View Source, Ctrl+U). Utiliser ensuite scripts/import_local.py."
        ),
    }
    print(json.dumps(protocol, ensure_ascii=False, indent=2))
    return 0


def save_outputs(
    url: str,
    output_dir: str,
    label: str,
    source_path: str | None,
    rendered_path: str | None,
) -> int:
    """Sauvegarde les outputs fournis par l'agent après exécution Playwright."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    result_source = None
    result_rendered = None
    framework = None
    warnings = []

    if source_path:
        src = Path(source_path)
        if src.exists():
            target = out / f"{label}-source.html"
            target.write_text(src.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            result_source = str(target)
        else:
            warnings.append(f"Source file not found: {source_path}")

    if rendered_path:
        rnd = Path(rendered_path)
        if rnd.exists():
            html = rnd.read_text(encoding="utf-8", errors="replace")
            target = out / f"{label}-rendered.html"
            target.write_text(html, encoding="utf-8")
            result_rendered = str(target)
            framework = detect_framework(html)
        else:
            warnings.append(f"Rendered file not found: {rendered_path}")

    if not result_source and not result_rendered:
        result = {
            "success": False,
            "url": url,
            "label": label,
            "reason": "Aucun fichier valide fourni (ni source ni rendered)",
            "suggestion": "Vérifier que les chemins fournis à --save-source / --save-rendered existent",
            "warnings": warnings,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    result = {
        "success": True,
        "url": url,
        "label": label,
        "mode": "authenticated",
        "file_source": result_source,
        "file_rendered": result_rendered,
        "is_spa": framework is not None,
        "framework_detected": framework,
        "fetched_at": datetime.now().isoformat(),
        "warnings": warnings,
        "note": (
            "Audit en mode authentifié. Le HTML source n'est pas toujours récupérable "
            "de la même façon que pour un site public. Privilégier le DOM rendu pour l'analyse."
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[fetch_authenticated] ✓ {label} (rendered={bool(result_rendered)}, source={bool(result_source)})", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch authenticated URL (Playwright MCP)")
    parser.add_argument("--url", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--label", default="page")
    parser.add_argument(
        "--emit-protocol",
        action="store_true",
        help="Mode 1 : générer le protocole que l'agent doit suivre avec Playwright",
    )
    parser.add_argument("--save-source", help="Mode 2 : chemin du fichier HTML source à sauvegarder")
    parser.add_argument("--save-rendered", help="Mode 2 : chemin du fichier HTML rendu à sauvegarder")

    args = parser.parse_args()

    if args.emit_protocol:
        return emit_protocol(args.url, args.output_dir, args.label)

    if args.save_source or args.save_rendered:
        return save_outputs(args.url, args.output_dir, args.label, args.save_source, args.save_rendered)

    print("[fetch_authenticated] ERROR: use --emit-protocol OR --save-source/--save-rendered", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
