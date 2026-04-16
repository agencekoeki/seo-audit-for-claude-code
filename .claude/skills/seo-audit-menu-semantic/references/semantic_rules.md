# Règles HTML sémantique pour les menus de navigation

Sources primaires :
- HTML Living Standard (WHATWG) : https://html.spec.whatwg.org/multipage/sections.html#the-nav-element
- WAI-ARIA 1.2 : https://www.w3.org/TR/wai-aria-1.2/
- WCAG 2.1 / 2.2 : https://www.w3.org/WAI/WCAG21/quickref/

## Règle 1 — Élément `<nav>` obligatoire

**Spec HTML5** : "The nav element represents a section of a page that links to other pages or to parts within the page: a section with navigation links."

**Vérifications :**
- ✅ Au moins un `<nav>` doit exister sur chaque page
- ✅ Si plusieurs `<nav>` (main nav + footer nav + sidebar nav), chacun DOIT avoir `aria-label` ou `aria-labelledby` distinct
- ❌ Pas de `<nav>` du tout → **BLOQUANT** (code `NO_NAV_ELEMENT`)
- ⚠️ Plusieurs `<nav>` sans aria-label distinctif → **IMPORTANT** (code `NAV_NO_ARIA_LABEL`)

**Exemple correct :**
```html
<nav aria-label="Navigation principale">...</nav>
<nav aria-label="Navigation footer">...</nav>
<nav aria-label="Fil d'Ariane">...</nav>
```

## Règle 2 — Structure `<ul>/<li>/<a>`

**Spec** : L'usage de `<ul>` (unordered list) est fortement recommandé pour les menus selon WHATWG, et standard selon WAI-ARIA Authoring Practices.

**Vérifications :**
- ✅ Structure attendue : `<nav><ul><li><a href>...</a></li></ul></nav>`
- ✅ Pour les sous-menus : `<li><a><ul><li>...</li></ul></li>`
- ⚠️ `<nav>` avec liens directs (pas de `<ul>`) → **IMPORTANT** (code `NAV_WITHOUT_UL_LI`)
  - Fonctionne mais moins sémantique, moins classifié correctement par Screaming Frog
  - Les lecteurs d'écran annoncent "menu de X items" grâce à la structure UL

## Règle 3 — Liens crawlables

**Spec Google Search Central** : "Links are only crawlable if they are `<a>` elements with an `href` attribute."

**Vérifications :**
- ✅ Chaque lien de navigation = `<a href="URL">`
- ❌ `<a>` sans `href` → **BLOQUANT** (code `MISSING_HREF`)
- ❌ `<a href="#">` → **BLOQUANT** (code `HASH_ONLY_HREF`)
- ❌ `<a href="javascript:void(0)">` → **BLOQUANT** (code `JAVASCRIPT_HREF`)
- ❌ `<div onclick="location.href='...'">` → **BLOQUANT** (code `DIV_ONCLICK_AS_LINK`)
- ❌ `<span onclick>` comme lien → **BLOQUANT** (code `SPAN_ONCLICK_AS_LINK`)
- ❌ `<button onclick>` pour navigation (pas une action) → **CRITIQUE** (code `BUTTON_AS_NAV_LINK`)

**Exception** : un `<button>` pour toggle le menu hamburger est OK. La distinction : est-ce une action (ouvrir/fermer) ou une navigation (aller sur une page) ?

## Règle 4 — Attributs ARIA

### `aria-label` sur `<nav>`

**WCAG 2.4.6** (AA) : Les labels décrivent la destination ou la fonction des liens.

- ✅ Obligatoire si plusieurs `<nav>` sur la page
- ✅ Recommandé même avec un seul `<nav>` pour plus de clarté
- Format : court et descriptif ("Navigation principale", "Fil d'Ariane", "Navigation footer")

### `aria-current="page"`

**WAI-ARIA 1.2** : Indique la page active dans un ensemble de pages liées.

- ✅ Recommandé sur le lien correspondant à la page courante
- Valeurs : `page` (la plus courante), `step`, `location`, `date`, `time`, `true`, `false`
- Aide les lecteurs d'écran ET signale à Google la structure de navigation

### `aria-expanded`

**WAI-ARIA 1.2** : Indique si un élément contrôlable est ouvert ou fermé.

- ✅ Obligatoire sur les boutons qui togglent un sous-menu ou menu mobile
- Valeurs : `true` (menu ouvert) ou `false` (menu fermé)
- Mise à jour dynamique via JS quand l'utilisateur interagit

### `aria-haspopup`

**WAI-ARIA 1.2** : Indique qu'un élément a un sous-menu/popup.

- ✅ Recommandé sur les liens top-level qui ouvrent un sous-menu
- Valeurs : `true`, `menu`, `listbox`, `tree`, `grid`, `dialog`

## Règle 5 — Landmarks HTML5

**ARIA Landmark Roles** : https://www.w3.org/TR/wai-aria-practices-1.2/#aria_landmark

Les 5 landmarks principaux à auditer :
- `<header>` → rôle `banner` implicite (si enfant direct de `<body>`)
- `<nav>` → rôle `navigation` implicite
- `<main>` → rôle `main` implicite
- `<footer>` → rôle `contentinfo` implicite (si enfant direct de `<body>`)
- `<aside>` → rôle `complementary` implicite

**Vérifications :**
- ✅ `<main>` présent → **OK**
- ⚠️ `<main>` absent → **IMPORTANT** (code `NO_MAIN_ELEMENT`)
  - Sans `<main>`, Google a plus de difficulté à séparer le boilerplate du contenu principal
  - Les lecteurs d'écran n'ont pas de "skip to main content" facile

## Règle 6 — Cohérence inter-pages

**Principe** : le menu doit avoir la MÊME structure sémantique sur toutes les pages du site. Sinon, Google peut interpréter la navigation différemment selon la page.

**Vérifications (si plusieurs pages fournies) :**
- Même nombre de `<nav>` ? (idéalement)
- Mêmes `aria-label` ? (obligatoire)
- Même structure `<ul>/<li>` ? (obligatoire)
- Ancres identiques pour les mêmes URLs ? (oui, sauf si contexte justifie)

Incohérences → flag comme **IMPORTANT** (code `INCONSISTENT_MENU_ACROSS_PAGES`).

## Anti-patterns à signaler

| Pattern | Sévérité | Raison |
|---------|----------|--------|
| `<nav>` imbriqué dans `<nav>` | Important | Non valide selon HTML5 |
| `role="navigation"` sur un `<div>` au lieu de `<nav>` | Important | Préférer l'élément sémantique natif |
| `<ol>` au lieu de `<ul>` pour un menu non séquentiel | Recommandation | L'ordre n'est pas sémantiquement significatif |
| Liens dans un `<section>` sans `<nav>` parent | Important | Screaming Frog ne les classifie pas comme navigation |
| Trop de `<nav>` (> 5) | Recommandation | Peut diluer le signal de "navigation principale" |

## Format JSON de sortie attendu

```json
{
  "agent": "seo-audit-menu-semantic",
  "audit_id": "...",
  "analyzed_at": "ISO",
  "pages_analyzed": ["homepage", "page-profonde"],
  "findings": [
    {
      "severity": "bloquant|critique|important|recommandation",
      "dimension": "semantic_html",
      "code": "CODE_UNIQUE",
      "message": "Description courte",
      "detail": "Explication + source (ex: 'WCAG 2.4.6 niveau AA')",
      "evidence": "<extrait HTML>",
      "pages_concerned": ["homepage"],
      "url": ""
    }
  ],
  "summary": {
    "verdict": "OK|ATTENTION|RISQUE_ELEVE|BLOQUANT",
    "total_findings": N,
    "by_severity": {"bloquant": 0, "critique": 1, "important": 3}
  },
  "i_know": ["Faits vérifiés dans le HTML fourni"],
  "i_think": ["Interprétations basées sur WCAG/W3C"],
  "i_cannot_verify": ["Ce qui nécessiterait un test live (lecteur d'écran, clavier)"]
}
```
