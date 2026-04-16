---
name: seo-audit-menu-parser
description: Parsing HTML d'un menu de navigation en structure de données typée (URLs, ancres, attributs ARIA, profondeurs, patterns problématiques). Skill utilisé par la plupart des agents d'audit de menu comme brique de base. Produit un JSON consolidé réutilisable.
---

# Skill : Parser HTML de menu

Ce skill fournit les briques de parsing HTML pour extraire la structure d'un menu de navigation. Il est utilisé par la majorité des agents d'audit (semantic, link-equity, crawlability, accessibility, performance, architecture).

## Script principal

**`scripts/parse_nav.py`** — Parse un HTML et produit un JSON structuré.

### Utilisation

```bash
python3 .claude/skills/seo-audit-menu-parser/scripts/parse_nav.py \
  --html path/to/page.html \
  --label "Homepage" \
  --output audits/{AUDIT_ID}/findings/parsed-homepage.json
```

Arguments :
- `--html PATH` : fichier HTML à parser
- `--stdin` : alternative, lire HTML sur stdin
- `--label TEXT` : label de la page (utilisé dans le JSON)
- `--output PATH` : chemin du fichier de sortie (sinon stdout)
- `--pretty` : pretty-print JSON (défaut: true)

### Ce que le script extrait

1. **Tous les éléments `<nav>`** avec leurs attributs (`aria-label`, `role`, `id`, `class`)
2. **Chaque lien dans chaque `<nav>`** :
   - `href`, texte d'ancre, profondeur dans les `<ul>/<li>`
   - Attributs `rel`, `target`, `aria-label`, `aria-current`, `class`, `title`
   - Détection `onclick` (problématique)
3. **Structure sémantique globale** : présence de `<header>`, `<main>`, `<footer>`
4. **Métriques** : nombre total de liens, liens top-level, URLs uniques, duplications, ratio nav/total
5. **Issues détectées automatiquement** (pour les problèmes détectables au parsing) :
   - `NAV_NO_ARIA_LABEL`
   - `MISSING_HREF`
   - `HASH_ONLY_HREF`
   - `JAVASCRIPT_HREF`
   - `ONCLICK_NO_HREF`
   - `NOFOLLOW_IN_NAV`
   - `EMPTY_ANCHOR_TEXT`
   - `DIV_ONCLICK_AS_LINK`
   - `SPAN_ONCLICK_AS_LINK`

### Format de sortie JSON

```json
{
  "meta": {
    "extraction_date": "ISO",
    "page_label": "Homepage",
    "source": "path/to/page.html",
    "total_html_chars": 12345,
    "parser_version": "0.2.0"
  },
  "semantic_structure": {
    "has_header": true,
    "has_nav": true,
    "has_main": true,
    "has_footer": true,
    "nav_count": 2,
    "semantic_elements_found": ["header", "main", "nav", "footer"]
  },
  "navs": [
    {
      "nav_index": 1,
      "aria_label": "Navigation principale",
      "aria_labelledby": "",
      "role": "",
      "id": "main-nav",
      "class": "header-nav",
      "link_count": 15,
      "max_depth": 2,
      "uses_ul_li": true,
      "links": [
        {
          "href": "/services",
          "text": "Services SEO",
          "depth": 1,
          "rel": "",
          "target": "",
          "aria_label": "",
          "aria_current": "",
          "class": "",
          "title": "",
          "onclick": "",
          "raw_issues": []
        }
      ]
    }
  ],
  "metrics": {
    "total_nav_links": 15,
    "top_level_links": 5,
    "unique_urls": 14,
    "duplicate_urls_in_nav": {"/contact": 2},
    "total_links_in_document": 25,
    "header_links": 15,
    "footer_links": 10,
    "nav_to_total_ratio": 60.0
  },
  "issues": [
    {
      "severity": "bloquant|critique|important|recommandation",
      "dimension": "...",
      "code": "...",
      "message": "...",
      "detail": "...",
      "url": "",
      "evidence": ""
    }
  ],
  "issue_summary": {"bloquant": 0, "critique": 1, "important": 3},
  "all_nav_urls": ["..."],
  "all_nav_anchors": [{"text": "...", "href": "...", "depth": 0}]
}
```

## Codes de sortie

- `0` : parsing réussi
- `1` : fichier introuvable ou illisible
- `2` : HTML malformé (parsing partiel, JSON quand même produit avec warning)
- `3` : erreur inattendue (stack trace sur stderr)

## Règle d'honnêteté

Si le HTML est malformé ou incomplet, le script :
1. Continue le parsing best-effort
2. Ajoute une issue avec code `MALFORMED_HTML` dans le JSON de sortie
3. Imprime un warning sur stderr
4. Retourne code 2 (success partiel)

**Jamais de crash silencieux.** Toujours un JSON produit, même vide.
