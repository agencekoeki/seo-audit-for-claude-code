---
name: seo-audit-menu-semantic
description: Expertise HTML5 sémantique et ARIA pour les menus de navigation. Règles W3C, critères WCAG applicables, patterns sémantiques corrects et anti-patterns. Utilisé par l'agent seo-audit-menu-semantic.
---

# Skill : Expertise HTML sémantique

## Workflow standard

1. L'agent lit les pages parsées (ou lance le parser si nécessaire)
2. Applique les règles de `references/semantic_rules.md`
3. Produit un JSON de findings structuré

## Règles à appliquer

Voir `references/semantic_rules.md` pour la liste exhaustive et référencée.

Les 6 dimensions couvertes :
1. Présence/unicité du `<nav>` primaire
2. Structure `<ul>/<li>/<a href>`
3. Attributs ARIA (`aria-label`, `aria-current`, `aria-expanded`)
4. Patterns anti-sémantiques (`<div onclick>`, `<span onclick>`, `<button>` comme lien nav)
5. Landmarks HTML5 (`<header>`, `<nav>`, `<main>`, `<footer>`)
6. Cohérence inter-pages

## Scripts disponibles (v0.3)

**Directive d'appel.** L'agent DOIT appeler ces scripts pendant sa phase d'analyse et inclure les résultats dans son JSON de findings (`audits/{AUDIT_ID}/findings/semantic.json`).

### `scripts/breadcrumb_checks.py` — breadcrumbs HTML + JSON-LD
**DOIT** être appelé sur chaque page auditée qui a un breadcrumb. Pattern ARIA correct, JSON-LD BreadcrumbList valide, alignement HTML ↔ JSON-LD.
```bash
python3 breadcrumb_checks.py --input page.html --url URL --output results.json
```
Items checklist v0.3 : **5.1.1, 5.2.1, 5.2.2, 5.2.3**

### `scripts/viewport_content_parity.js` — parité contenu desktop/mobile
**DOIT** être appelé au moins sur la homepage de chaque version. Compare les blocs de texte visibles entre viewport desktop et mobile. Détecte les contenus masqués, les mots-clés de positionnement qui disparaissent, les variantes responsive. Chaque mismatch inclut `is_responsive_variant` pour filtrer les reformulations légitimes.
```bash
node viewport_content_parity.js --url URL --output results.json [--profile-dir PATH]
```
Items checklist v0.3 : **1.5.1**

## Format de sortie

JSON dans `audits/{AUDIT_ID}/findings/semantic.json` avec structure standard (voir CLAUDE.md projet).

Champs obligatoires du JSON :
- `agent: "seo-audit-menu-semantic"`
- `findings: []` avec severity/dimension/code/message/detail/evidence
- `i_know: []`, `i_think: []`, `i_cannot_verify: []`
- `summary` avec verdict
