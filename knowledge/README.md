# Knowledge Base — base de connaissances SEO transverse

Cette base contient les sources primaires et références SEO utilisées par les audits. Elle complète les `references/` spécifiques à chaque skill.

## Pourquoi cette knowledge base ?

Les `references/` dans les skills sont chargées dans le contexte de leur agent. Cette knowledge base globale sert à :
- Référence croisée quand plusieurs audits partagent une même source
- Import dans un Project Claude.ai pour brainstormer
- Documentation pour les nouveaux contributeurs

## Organisation

Les fichiers de `references/` les plus importants sont disponibles à travers tout le projet via cette knowledge base :

- **Brevets Google** → `.claude/skills/seo-audit-menu-link-equity/references/`
  - `reasonable_surfer.md` — Brevet US 7,716,225 / US 9,305,099
  - `boilerplate_patent.md` — Brevet US 8,898,296
  - `first_link_priority.md` — Matt Cutts, John Mueller
  - `quantitative_thresholds.md` — Seuils communautaires

- **Accessibilité** → `.claude/skills/seo-audit-menu-accessibility/references/`
  - `wcag_nav.md` — WCAG 2.1 / 2.2 appliqués aux menus
  - `mobile_first.md` — Mobile-first indexing et hamburger menus

- **Performance** → `.claude/skills/seo-audit-menu-performance/references/`
  - `cwv_thresholds.md` — Core Web Vitals et patterns menu

- **Structure HTML** → `.claude/skills/seo-audit-menu-semantic/references/`
  - `semantic_rules.md` — HTML5, ARIA, règles sémantiques

## Sources primaires référencées

### Brevets Google
1. **US 7,716,225** — Reasonable Surfer Model (2010)
   https://patents.google.com/patent/US7716225B1/en

2. **US 9,305,099** — Reasonable Surfer updated (2016)
   https://patents.google.com/patent/US9305099B1/en

3. **US 8,898,296** — Boilerplate Detection (2014)
   https://patents.google.com/patent/US8898296B2/en

### W3C / WHATWG
4. **HTML Living Standard** — https://html.spec.whatwg.org/
5. **WAI-ARIA 1.2** — https://www.w3.org/TR/wai-aria-1.2/
6. **WCAG 2.1** — https://www.w3.org/TR/WCAG21/
7. **WCAG 2.2** — https://www.w3.org/TR/WCAG22/

### Google Search Central
8. **Core Web Vitals** — https://web.dev/articles/vitals
9. **Mobile-first indexing** — https://developers.google.com/search/mobile-sites/mobile-first-indexing
10. **Page Experience** — https://developers.google.com/search/docs/appearance/page-experience

### Industry references
11. **Bill Slawski — SEO by the Sea** (décryptages brevets)
12. **Matt Cutts (2009)** — First Link Priority
13. **John Mueller (2021)** — confirmation partielle First Link Priority
14. **Sitebulb — Dena Warren (août 2025)** — Case study refonte menu

## Principe de rigueur

Chaque règle SEO appliquée dans un audit doit être traçable à l'une de ces sources. **Ne jamais inventer une règle** ou la citer comme "règle de Google" si elle ne vient pas d'une source officielle Google.

Distinction obligatoire dans les rapports :
- **JE SAIS** : fait vérifié dans les données de l'audit
- **JE PENSE** : interprétation basée sur une source ci-dessus
- **JE NE PEUX PAS VÉRIFIER** : nécessite accès live ou données complémentaires
