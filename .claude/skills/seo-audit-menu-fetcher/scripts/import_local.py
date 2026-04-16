#!/usr/bin/env python3
"""
import_local.py — Import d'un fichier HTML local ou depuis stdin.

Normalise les inputs locaux dans le même format que les autres fetchers,
pour que les agents d'analyse en aval traitent tous les inputs de la même façon.

Usage :
    python3 import_local.py --input page.html --output-dir DIR --label LABEL
    cat page.html | python3 import_local.py --stdin --output-dir DIR --label LABEL
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
}


def detect_framework(html: str) -> str | None:
    for name, patterns in SPA_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, html, re.IGNORECASE):
                return name
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Import local HTML file")
    parser.add_argument("--input", help="Path to local HTML file")
    parser.add_argument("--stdin", action="store_true", help="Read HTML from stdin")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--label", default="page")

    args = parser.parse_args()

    if args.stdin:
        html = sys.stdin.read()
        source_label = "stdin"
    elif args.input:
        src = Path(args.input)
        if not src.exists():
            result = {
                "success": False,
                "label": args.label,
                "reason": f"Fichier introuvable : {args.input}",
                "suggestion": "Vérifier le chemin fourni",
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        html = src.read_text(encoding="utf-8", errors="replace")
        source_label = str(src)
    else:
        print("[import_local] ERROR: use --input <path> OR --stdin", file=sys.stderr)
        return 1

    if not html.strip():
        result = {
            "success": False,
            "label": args.label,
            "reason": "HTML vide",
            "suggestion": "Vérifier le contenu du fichier ou de stdin",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{args.label}-source.html"
    target.write_text(html, encoding="utf-8")

    framework = detect_framework(html)

    result = {
        "success": True,
        "mode": "local",
        "source_input": source_label,
        "label": args.label,
        "file_source": str(target),
        "file_rendered": None,
        "size_bytes": len(html.encode("utf-8")),
        "is_spa": framework is not None,
        "framework_detected": framework,
        "imported_at": datetime.now().isoformat(),
    }

    if framework:
        result["note"] = (
            f"Framework {framework} détecté dans le HTML. "
            "Si l'utilisateur a fourni le HTML source (View Source / curl), "
            "demander aussi le HTML rendu (Chrome DevTools → Elements → Copy outer HTML de <html>) "
            "pour une analyse de crawlabilité complète."
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[import_local] ✓ {args.label} ({len(html)} chars)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
