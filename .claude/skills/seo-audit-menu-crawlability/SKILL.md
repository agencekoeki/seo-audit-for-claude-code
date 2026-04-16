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

## Format de sortie JSON

Standard. Voir CLAUDE.md projet.

Champs spécifiques à la dimension :
- `dimension: "crawlability"`
- Sous-dimensions possibles :
  - `source_vs_rendered_diff`
  - `js_framework_risk`
  - `onclick_without_href`
  - `hydration_pattern`
