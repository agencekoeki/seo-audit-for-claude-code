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

## Scripts disponibles (v0.3)

**Directive d'appel.** L'agent DOIT appeler les DEUX scripts (statique + dynamique) pendant sa phase d'analyse et inclure les résultats dans son JSON de findings (`audits/{AUDIT_ID}/findings/accessibility.json`). Le script statique ne remplace pas le dynamique — ils couvrent des items différents de la checklist.

### `scripts/accessibility_checks.py` — checks statiques ARIA/WCAG
**DOIT** être appelé sur chaque fichier HTML (source ou rendered). Analyse sans exécution JS : landmarks nav, anti-pattern role="menu", aria-current, outline:none, skip link, triggers button vs a.
```bash
python3 accessibility_checks.py --input page.html --url URL --output results.json
```
Items checklist v0.3 : **3.1.1, 3.1.2, 3.1.3, 3.1.4, 3.2.4, 3.4.2**

### `scripts/accessibility_dynamic.js` — tests dynamiques Playwright
**DOIT** être appelé en desktop ET en mobile sur chaque page auditée. Arbre ARIA (`page.accessibility.snapshot()`), Tab order réel, focus visibility via Tab clavier (:focus-visible), target sizes (getBoundingClientRect), Escape ferme le burger, aria-current.
```bash
node accessibility_dynamic.js --url URL --output results.json [--viewport desktop|mobile] [--profile-dir PATH]
```
Items checklist v0.3 : **3.2.1, 3.2.3, 3.3.1, 3.4.1, 3.4.3**

## Limites reconnues (JE NE PEUX PAS VÉRIFIER)

Avec les scripts v0.3, la plupart des tests sont maintenant couverts. Restent non vérifiables :
- Comportement des lecteurs d'écran spécifiques (NVDA, JAWS, VoiceOver) — nécessite test manuel
- Contraste des indicateurs de focus (nécessite analyse visuelle du screenshot)

→ Flagger ces aspects dans `i_cannot_verify`.

## Format de sortie JSON

Standard. Voir CLAUDE.md projet.
