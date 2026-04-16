#!/usr/bin/env python3
"""
test_parser.py — Tests unitaires du parser de menu.

Exécution :
    python3 -m pytest tests/test_parser.py
    ou
    python3 tests/test_parser.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
PARSER = REPO_ROOT / ".claude" / "skills" / "seo-audit-menu-parser" / "scripts" / "parse_nav.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_menu.html"


def run_parser(html_file: Path, label: str = "test") -> dict:
    """Lance le parser et retourne le JSON produit."""
    result = subprocess.run(
        [sys.executable, str(PARSER), "--html", str(html_file), "--label", label],
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 2), f"Parser failed: {result.stderr}"
    return json.loads(result.stdout)


def test_parser_finds_nav():
    data = run_parser(FIXTURE)
    assert data["semantic_structure"]["has_nav"] is True
    assert data["semantic_structure"]["nav_count"] == 2  # header + footer nav


def test_parser_finds_main():
    data = run_parser(FIXTURE)
    assert data["semantic_structure"]["has_main"] is True


def test_parser_finds_header_footer():
    data = run_parser(FIXTURE)
    assert data["semantic_structure"]["has_header"] is True
    assert data["semantic_structure"]["has_footer"] is True


def test_parser_detects_aria_label():
    data = run_parser(FIXTURE)
    main_nav = next(
        (n for n in data["navs"] if n["id"] == "main-nav"),
        None,
    )
    assert main_nav is not None
    assert main_nav["aria_label"] == "Navigation principale"


def test_parser_flags_nav_without_aria_label():
    data = run_parser(FIXTURE)
    codes = {i["code"] for i in data["issues"]}
    # Le footer nav n'a pas d'aria-label → devrait être flaggé
    assert "NAV_NO_ARIA_LABEL" in codes


def test_parser_flags_div_onclick():
    data = run_parser(FIXTURE)
    codes = {i["code"] for i in data["issues"]}
    assert "DIV_ONCLICK_AS_LINK" in codes


def test_parser_flags_hash_only_href():
    data = run_parser(FIXTURE)
    codes = {i["code"] for i in data["issues"]}
    assert "HASH_ONLY_HREF" in codes


def test_parser_flags_javascript_href():
    data = run_parser(FIXTURE)
    codes = {i["code"] for i in data["issues"]}
    assert "JAVASCRIPT_HREF" in codes


def test_parser_counts_links():
    data = run_parser(FIXTURE)
    # main nav: 5 top-level + 3 sub = 8, dont certains avec href problématique
    # footer nav: 4
    total = data["metrics"]["total_nav_links"]
    assert total >= 10, f"Expected at least 10 nav links, got {total}"


def test_parser_detects_duplicate_urls():
    data = run_parser(FIXTURE)
    duplicates = data["metrics"]["duplicate_urls_in_nav"]
    # /contact est dans le menu principal ET le footer
    assert "/contact" in duplicates
    assert duplicates["/contact"] == 2


def test_parser_extracts_anchors():
    data = run_parser(FIXTURE)
    anchors = {a["text"]: a["href"] for a in data["all_nav_anchors"] if a["text"]}
    assert "Services" in anchors
    assert anchors["Services"] == "/services"
    assert "Tarifs" in anchors
    assert "Contact" in anchors


def test_parser_issue_summary():
    data = run_parser(FIXTURE)
    summary = data["issue_summary"]
    # La fixture est volontairement piégée → au moins un bloquant
    assert summary["bloquant"] >= 1, f"Expected at least 1 bloquant, got {summary}"


if __name__ == "__main__":
    # Exécution manuelle : lance tous les tests et affiche un résumé
    test_fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for fn in test_fns:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {fn.__name__}: UNEXPECTED {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed (total {len(test_fns)})")
    sys.exit(0 if failed == 0 else 1)
