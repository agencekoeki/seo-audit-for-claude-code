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

## Format de sortie

JSON dans `audits/{AUDIT_ID}/findings/semantic.json` avec structure standard (voir CLAUDE.md projet).

Champs obligatoires du JSON :
- `agent: "seo-audit-menu-semantic"`
- `findings: []` avec severity/dimension/code/message/detail/evidence
- `i_know: []`, `i_think: []`, `i_cannot_verify: []`
- `summary` avec verdict
