#!/usr/bin/env python3
"""
audit_completeness_checker.py — Vérifie la complétude d'un run d'audit.

Vérifie de manière 100% déterministe que chaque étape du pipeline a produit
son output, que chaque script a un status != "error", et que chaque test
a elements_checked > 0 quand passed == true.

Usage :
    python3 tools/audit_completeness_checker.py --audit-dir audits/YYYYMMDD-site/

Code de sortie :
    0 : PASS
    1 : WARN (trous documentés)
    2 : FAIL (trous non documentés ou fichiers manquants)
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import sys
from pathlib import Path

# Forcer UTF-8 sur stdout pour Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# Fichiers attendus (patterns glob relatifs au dossier d'audit)
REQUIRED_FILES = {
    "pages/*-rendered.html": "Fetch Playwright (au moins 1 page)",
    "pages/*-burger.json": "Capture burger mobile",
    "findings/*.json": "Findings des spécialistes (au moins 1)",
    "consolidation.md": "Consolidation orchestrateur",
    "reports/report-draft.md": "Rapport draft",
}

OPTIONAL_FILES = {
    "pages/*-source.html": "Fetch curl (HTML source pré-JS)",
    "reports/report-draft.html": "Rapport HTML",
    "review.json": "Review pré-rédaction",
    "reports/review-notes.md": "Notes de review",
}


def check_files(audit_dir: Path) -> tuple[list[str], list[str], list[str]]:
    """Vérifie les fichiers attendus. Retourne (passes, warns, fails)."""
    passes, warns, fails = [], [], []

    for pattern, desc in REQUIRED_FILES.items():
        matches = list(audit_dir.glob(pattern))
        if matches:
            passes.append(f"  ✓ {pattern} ({len(matches)} fichier(s)) — {desc}")
        else:
            fails.append(f"  ✗ {pattern} (0 fichiers) — {desc}")

    for pattern, desc in OPTIONAL_FILES.items():
        matches = list(audit_dir.glob(pattern))
        if matches:
            passes.append(f"  ✓ {pattern} ({len(matches)} fichier(s)) — {desc}")
        else:
            warns.append(f"  ⚠ {pattern} (0 fichiers) — {desc} [optionnel]")

    return passes, warns, fails


def check_script_statuses(audit_dir: Path) -> tuple[list[str], list[str], list[str]]:
    """Vérifie le champ status dans chaque JSON de findings."""
    passes, warns, fails = [], [], []
    findings_dir = audit_dir / "findings"
    if not findings_dir.exists():
        return passes, warns, ["  ✗ Dossier findings/ absent"]

    for f in sorted(findings_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            fails.append(f"  ✗ {f.name} : JSON invalide ({e})")
            continue

        if not isinstance(data, dict):
            continue

        status = data.get("status", "MISSING")
        if status == "error":
            detail = data.get("status_detail", "pas de détail")
            fails.append(f"  ✗ {f.name} : status=error — {detail}")
        elif status == "partial":
            detail = data.get("status_detail", "pas de détail")
            warns.append(f"  ⚠ {f.name} : status=partial — {detail}")
        elif status in ("complete", "MISSING"):
            passes.append(f"  ✓ {f.name} : status={status}")
        else:
            warns.append(f"  ⚠ {f.name} : status inconnu '{status}'")

    return passes, warns, fails


def check_silent_failures(audit_dir: Path) -> tuple[list[str], list[str]]:
    """Détecte les tests avec elements_checked=0 et passed=true."""
    warns, fails = [], []
    findings_dir = audit_dir / "findings"
    if not findings_dir.exists():
        return warns, fails

    for f in sorted(findings_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        if not isinstance(data, dict):
            continue

        for test in data.get("tests", []):
            if not isinstance(test, dict):
                continue
            ec = test.get("elements_checked", test.get("total_checked", -1))
            passed = test.get("passed")
            test_name = test.get("test", "inconnu")

            if ec == 0 and passed is True:
                warns.append(
                    f"  ⚠ {f.name} > {test_name} : elements_checked=0 avec passed=true → échec silencieux"
                )

    return warns, fails


def check_report(audit_dir: Path) -> tuple[list[str], list[str], list[str]]:
    """Vérifie le contenu du rapport final."""
    passes, warns, fails = [], [], []
    report_path = audit_dir / "reports" / "report-draft.md"
    if not report_path.exists():
        return passes, warns, ["  ✗ reports/report-draft.md absent"]

    report = report_path.read_text(encoding="utf-8", errors="replace").lower()

    required_sections = [
        "verdict",  # synthèse exécutive / verdict banner
        "bloquant",
        "critique",
        "important",
        "recommandation",
    ]
    methodology_keywords = ["je sais", "savoir", "je pense", "penser", "vérifier"]

    for section in required_sections:
        if section in report:
            passes.append(f"  ✓ Section '{section}' présente")
        else:
            fails.append(f"  ✗ Section '{section}' absente du rapport")

    meth_found = any(kw in report for kw in methodology_keywords)
    if meth_found:
        passes.append("  ✓ Section méthodologie (SAVOIR/PENSER/VÉRIFIER) présente")
    else:
        fails.append("  ✗ Section méthodologie (SAVOIR/PENSER/VÉRIFIER) absente")

    banned_phrases = [
        "à vous de vérifier",
        "ouvrir le menu burger",
        "vérifier manuellement",
    ]
    for phrase in banned_phrases:
        if phrase in report:
            fails.append(f"  ✗ Phrase interdite trouvée : '{phrase}'")

    return passes, warns, fails


def main() -> int:
    parser = argparse.ArgumentParser(description="Vérifie la complétude d'un run d'audit")
    parser.add_argument("--audit-dir", required=True, help="Dossier de l'audit")
    args = parser.parse_args()

    audit_dir = Path(args.audit_dir)
    if not audit_dir.exists():
        print(f"[completeness] ✗ Dossier introuvable : {args.audit_dir}", file=sys.stderr)
        return 2

    all_passes, all_warns, all_fails = [], [], []

    print("=== AUDIT COMPLETENESS CHECK ===\n")

    # Niveau 1
    print("NIVEAU 1 — Fichiers attendus")
    p, w, f = check_files(audit_dir)
    all_passes.extend(p); all_warns.extend(w); all_fails.extend(f)
    for line in p + w + f:
        print(line)

    # Niveau 2
    print("\nNIVEAU 2 — Status des scripts")
    p, w, f = check_script_statuses(audit_dir)
    all_passes.extend(p); all_warns.extend(w); all_fails.extend(f)
    for line in p + w + f:
        print(line)

    # Niveau 3
    print("\nNIVEAU 3 — Échecs silencieux")
    w, f = check_silent_failures(audit_dir)
    all_warns.extend(w); all_fails.extend(f)
    if not w and not f:
        print("  ✓ Aucun échec silencieux détecté")
    for line in w + f:
        print(line)

    # Niveau 4
    print("\nNIVEAU 4 — Rapport")
    p, w, f = check_report(audit_dir)
    all_passes.extend(p); all_warns.extend(w); all_fails.extend(f)
    for line in p + w + f:
        print(line)

    # Verdict
    print()
    if all_fails:
        print(f"=== VERDICT : FAIL ===")
        print(f"{len(all_fails)} erreur(s), {len(all_warns)} avertissement(s)")
        print("Action requise : corriger les erreurs avant livraison.")
        return 2
    elif all_warns:
        print(f"=== VERDICT : WARN ===")
        print(f"{len(all_warns)} avertissement(s)")
        print("Les warnings sont documentés. L'humain décide de livrer ou non.")
        return 1
    else:
        print(f"=== VERDICT : PASS ===")
        print("Tous les checks passent. Livraison OK.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
