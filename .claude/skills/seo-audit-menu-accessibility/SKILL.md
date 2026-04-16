---
name: seo-audit-menu-accessibility
description: Expertise mobile-first indexing et WCAG 2.1/2.2 pour les menus. Parité mobile/desktop, navigation clavier, ARIA, tap targets, hamburger menus. Utilisé par l'agent seo-audit-menu-accessibility.
---

# Skill : Accessibilité et mobile-first

## Workflow

1. Lire le parsing JSON
2. Appliquer les critères WCAG et les règles mobile-first
3. Produire findings structurés

## Références

- `references/wcag_nav.md` — Critères WCAG 2.1/2.2 applicables aux menus
- `references/mobile_first.md` — Mobile-first indexing Google + spécificités hamburger

## Dimensions à vérifier

1. Parité mobile/desktop (liens identiques dans les deux versions)
2. Hamburger menu : liens dans DOM initial vs injectés au clic
3. Navigation clavier (Tab, Shift+Tab, Enter, Escape)
4. Attributs ARIA (aria-label, aria-current, aria-expanded, aria-haspopup)
5. Focus management (indicateur visible, ordre logique)
6. Tap targets (44x44px iOS, 48x48px Material)
7. Skip link présent en début de body
8. CSS `display: none` sous media query sans remplacement

## Limites reconnues (JE NE PEUX PAS VÉRIFIER)

Sans accès live, on ne peut pas vérifier :
- Comportement réel au clavier (Tab, focus visible)
- Rendu du focus (CSS `:focus-visible`)
- Taille effective des tap targets (CSS computed values)
- Comportement des lecteurs d'écran (NVDA, JAWS, VoiceOver)
- Ordre de lecture réel du DOM

→ Toujours flagger ces aspects dans `i_cannot_verify` et recommander des outils live (axe, WAVE, Lighthouse A11Y).

## Format de sortie JSON

Standard. Voir CLAUDE.md projet.
