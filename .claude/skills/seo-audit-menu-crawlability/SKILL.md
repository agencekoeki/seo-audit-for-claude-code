---
name: seo-audit-menu-crawlability
description: Expertise crawl et rendering. Compare HTML source (première passe Googlebot) vs DOM rendu (après JS). Détection de SPAs, hydratation, liens invisibles au crawl. Utilisé par l'agent seo-audit-menu-crawlability.
---

# Skill : Expertise crawl & rendering

## Workflow

1. Lire `audits/{AUDIT_ID}/pages/` pour trouver `*-source.html` et `*-rendered.html`
2. Si les deux fichiers sont présents : lancer le script de diff
3. Sinon : analyser le HTML source seul et flagger comme "JE NE PEUX PAS VÉRIFIER" pour les aspects nécessitant le DOM rendu

## Script

**`scripts/diff_source_vs_rendered.py`** — compare les deux versions d'une même page.

### Utilisation

```bash
python3 .claude/skills/seo-audit-menu-crawlability/scripts/diff_source_vs_rendered.py \
  --source audits/{AUDIT_ID}/pages/homepage-source.html \
  --rendered audits/{AUDIT_ID}/pages/homepage-rendered.html \
  --output audits/{AUDIT_ID}/findings/crawlability-diff.json
```

### Ce qu'il détecte

1. Liens présents dans rendu mais absents du source → **INVISIBLE au crawl 1ère passe**
2. URLs uniques : set source vs set rendered → diff
3. Ancres pour mêmes URLs : différentes entre source et rendu ?
4. Nombre de `<nav>` source vs rendered
5. Framework détecté : React, Vue, Angular, Next, Nuxt, Gatsby, Remix...

## Règles d'interprétation

### SSR correct (Server-Side Rendering)

Si source.nav_links ≈ rendered.nav_links (même nombre, mêmes URLs) → SSR opérationnel → OK

### SSR partiel / hydratation

Si source a quelques liens (logo, skip link) mais rendered a le vrai menu → le menu est client-side only → **BLOQUANT**

### CSR pur (Client-Side Rendering)

Si source n'a AUCUN lien et rendered en a 30 → CSR pur → **BLOQUANT**
- Googlebot peut voir le DOM rendu en seconde vague, mais :
- Gros sites : budget de rendu JS très contraint
- Sites récents : peut prendre jours/semaines pour que Google finisse le rendering

### Pas de rendered disponible

Si l'agent n'a que le source (Playwright pas lancé) :
- Détecter patterns à risque (`onclick` sans href, frameworks JS dans `<script>`)
- Flagger comme "JE NE PEUX PAS VÉRIFIER" au lieu de conclure à l'aveugle
- Recommander à l'utilisateur de fournir le DOM rendu

## Scripts disponibles (v0.3)

**Directive d'appel.** L'agent DOIT appeler chaque script pertinent pendant sa phase d'analyse et inclure les résultats dans son JSON de findings (`audits/{AUDIT_ID}/findings/crawlability.json`). Un script non appelé = un trou dans la couverture de l'audit.

### `scripts/diff_source_vs_rendered.py` — diff source vs rendu
Voir ci-dessus. **DOIT** être appelé quand source ET rendered sont disponibles.

### `scripts/url_status_checker.py` — statut HTTP de chaque URL du menu
**DOIT** être appelé sur toutes les URLs du menu + breadcrumbs. Vérifie les redirections, meta robots, X-Robots-Tag. Parallélisé (8 workers).
```bash
python3 url_status_checker.py --input urls.json --output statuses.json [--insecure] [--cookies-from-playwright-profile PATH]
```
Items checklist v0.3 : **1.4.3, 9.2.1, 9.2.2**

### `scripts/sitemap_alignment.py` — croisement menu vs sitemap vs robots.txt
**DOIT** être appelé une fois par version auditée. Parse robots.txt, fetch sitemaps récursifs, détecte URLs du menu absentes ou bloquées.
```bash
python3 sitemap_alignment.py --site-url https://example.com --menu-urls menu_urls.json --output results.json [--insecure]
```
Items checklist v0.3 : **1.4.1, 1.4.2**

### `scripts/i18n_checks.py` — cohérence hreflang et sélecteur de langue
**DOIT** être appelé sur chaque page auditée. Détecte sélecteur de langue, parse hreflang, vérifie self-reference et x-default.
```bash
python3 i18n_checks.py --input page.html --url URL --output results.json
```
Items checklist v0.3 : **7.1.1, 7.1.2, 7.1.3**

### `scripts/css_analyzer.py` — media queries hostiles au mobile-first
**DOIT** être appelé sur chaque page auditée (avec `--base-url` pour fetcher les CSS externes). Analyse CSS inline + fetch des 5 premières feuilles externes. Détecte nav display:none, desktop-first patterns, :hover sans :focus.
```bash
python3 css_analyzer.py --input page.html --output results.json --base-url https://example.com [--insecure]
```
Items checklist v0.3 : **1.5.3, 3.2.2**

### `scripts/fetch_googlebot.js` — test cloaking UA Googlebot
**DOIT** être appelé au moins sur la homepage. Fetch avec UA Chrome standard puis UA Googlebot Smartphone, diff des liens nav.
```bash
node fetch_googlebot.js --url URL --output results.json [--profile-dir PATH]
```
Items checklist v0.3 : **1.1.3**

## Format de sortie JSON

Standard. Voir CLAUDE.md projet.

Champs spécifiques à la dimension :
- `dimension: "crawlability"`
- Sous-dimensions possibles :
  - `source_vs_rendered_diff`
  - `js_framework_risk`
  - `onclick_without_href`
  - `hydration_pattern`
  - `url_status`
  - `sitemap_alignment`
  - `i18n`
  - `css_mobile_first`
  - `cloaking`
