# Menu Audit Checklist v0.3 — Référentiel exhaustif des risques SEO sur les menus de navigation

**Document source pour le toolkit `seo-audit-for-claude-code`.**
**Objectif** : formaliser l'intégralité des risques SEO spécifiques aux menus de navigation, avec distinction rigoureuse **SAVOIR / PENSER / PAS VÉRIFIER**, et spécification de testabilité pour chaque item.

---

## Conventions

- **[SAVOIR]** : source primaire vérifiable (brevet, doc Google, norme W3C)
- **[PENSER]** : bonne pratique communautaire, inférence raisonnable
- **[PAS VÉRIFIER]** : dépend de données non publiques Google
- **[STATIC]** : scriptable Python pur (html.parser, regex)
- **[DYNAMIC]** : nécessite Playwright (rendu JS, interaction, mesure perf)
- **[LLM]** : jugement qualitatif par l'agent
- **[EXTERNAL]** : données externes (GSC, Ahrefs, logs serveur)
- Sévérité : BLOQUANT / CRITIQUE / IMPORTANT / RECOMMANDATION

---

## Tableau récapitulatif des 67 tests

| ID | Test | Type | Script cible |
|----|------|------|--------------|
| 1.1.1 | Liens nav dans source pré-JS | STATIC+DYNAMIC | diff_source_vs_rendered.py |
| 1.1.2 | Détection framework | STATIC | parse_nav.py |
| 1.1.3 | User-Agent Googlebot diff | DYNAMIC | fetch_googlebot.js |
| 1.2.1 | Click depth pages stratégiques | STATIC+EXTERNAL | parse_nav.py + crosscheck |
| 1.2.2 | Profondeur menu | STATIC | parse_nav.py |
| 1.3.1 | Liens injectés après interaction | DYNAMIC | diff_source_vs_rendered.py |
| 1.3.2 | Hover sans focus equivalent | STATIC+DYNAMIC | accessibility_checks.py |
| 1.3.3 | Off-canvas drawer SSR | DYNAMIC | diff_source_vs_rendered.py |
| 1.4.1 | URLs menu → sitemap | STATIC | sitemap_alignment.py |
| 1.4.2 | Menu → robots.txt | STATIC | sitemap_alignment.py |
| 1.4.3 | Meta robots noindex menu URLs | STATIC | url_status_checker.py |
| 1.5.1 | Parité menu mobile/desktop | DYNAMIC | viewport_parity.js |
| 1.5.2 | Viewport meta | STATIC | parse_nav.py |
| 1.5.3 | Media queries hostiles | STATIC+LLM | css_analyzer.py |
| 2.1.1 | Position nav dans DOM source | STATIC | parse_nav.py |
| 2.1.2 | Cohérence topicale | LLM | reasoning agent |
| 2.2.1 | Nombre total liens nav | STATIC | parse_nav.py |
| 2.2.2 | Ratio nav/contenu | STATIC | parse_nav.py |
| 2.2.3 | Duplication contenu mega menu | STATIC | parse_nav.py |
| 2.3.1 | Liens multiples même URL | STATIC | parse_nav.py |
| 2.3.2 | Collision logo + premier item | STATIC | parse_nav.py |
| 2.4.1 | Ancres génériques | STATIC | parse_nav.py |
| 2.4.2 | Ancres vides | STATIC | parse_nav.py |
| 2.4.3 | Diversité ancres par URL | STATIC | parse_nav.py |
| 2.4.4 | Cohérence ancres zones | STATIC | parse_nav.py |
| 2.5.1 | URLs footer-only | STATIC | parse_nav.py |
| 2.5.2 | Liens externes footer nofollow | STATIC | parse_nav.py |
| 2.6.1 | Hiérarchie thématique | LLM | reasoning agent |
| 3.1.1 | Balise `<nav>` | STATIC | parse_nav.py |
| 3.1.2 | Anti-pattern role="menu" | STATIC | accessibility_checks.py |
| 3.1.3 | Labels nav multiples | STATIC | accessibility_checks.py |
| 3.1.4 | aria-current="page" | STATIC | accessibility_checks.py |
| 3.2.1 | Focus Appearance WCAG 2.2 | DYNAMIC | accessibility_dynamic.js |
| 3.2.2 | Hover on Focus WCAG 2.2 | STATIC+DYNAMIC | accessibility_checks.py |
| 3.2.3 | Target Size 24x24 | DYNAMIC | accessibility_dynamic.js |
| 3.2.4 | Focus Visible | STATIC | accessibility_checks.py |
| 3.3.1 | Skip link | STATIC | accessibility_checks.py |
| 3.4.1 | Escape ferme sous-menu | DYNAMIC | accessibility_dynamic.js |
| 3.4.2 | Trigger = button | STATIC | accessibility_checks.py |
| 3.4.3 | Focus management | DYNAMIC | accessibility_dynamic.js |
| 4.1.1 | INP 200ms | DYNAMIC | performance_checks.js |
| 4.1.2 | Event handlers lourds | STATIC+LLM | reasoning agent |
| 4.2.1 | Sticky header CLS | DYNAMIC | performance_checks.js |
| 4.2.2 | Hauteur header hydratation | DYNAMIC | performance_checks.js |
| 4.2.3 | Occupation viewport mobile | DYNAMIC | performance_checks.js |
| 4.3.1 | Menu comme LCP | DYNAMIC | performance_checks.js |
| 4.3.2 | Scripts bloquants avant menu | STATIC | parse_nav.py |
| 5.1.1 | Pattern breadcrumb ARIA | STATIC | breadcrumb_checks.py |
| 5.2.1 | JSON-LD BreadcrumbList | STATIC | breadcrumb_checks.py |
| 5.2.2 | Alignement HTML → JSON-LD | STATIC | breadcrumb_checks.py |
| 5.2.3 | URLs absolues dans item | STATIC | breadcrumb_checks.py |
| 6.1.1 | Facettes dans menu | STATIC | parse_nav.py |
| 6.1.2 | rel=nofollow sur facettes | STATIC | parse_nav.py |
| 7.1.1 | Sélecteur menu → hreflang | STATIC | i18n_checks.py |
| 7.1.2 | Self-referencing hreflang | STATIC | i18n_checks.py |
| 7.1.3 | x-default | STATIC | i18n_checks.py |
| 8.1.1 | Statut HTTP URLs supprimées | STATIC | compare_menus.py |
| 8.1.2 | Changement ancre même URL | STATIC | compare_menus.py |
| 8.2.1 | URLs nouvelles | STATIC+LLM | compare_menus.py + reasoning |
| 9.2.1 | Liens brisés 4xx/5xx | STATIC | url_status_checker.py |
| 9.2.2 | Redirects domaines externes | STATIC | url_status_checker.py |
| 9.3.1 | Parité multi-templates | DYNAMIC | orchestrator multi-fetch |
| 10.1 | SiteNavigationElement schema | STATIC | parse_nav.py |
| 11.1.1 | Nombre items top-level | STATIC | parse_nav.py |
| 11.1.2 | Labels jargon | LLM | reasoning agent |
| 11.2.1 | Search dans menu | STATIC | parse_nav.py |

---

Pour le détail complet de chaque test (description, référence épistémique, sources primaires, seuils de sévérité), voir le document source complet fourni au brief v0.3.
