# Core Web Vitals appliqués aux menus

## Sources primaires

- Google Web.dev — CWV : https://web.dev/articles/vitals
- Google Search Central — Page Experience : https://developers.google.com/search/docs/appearance/page-experience
- Chrome UX Report : https://developer.chrome.com/docs/crux/

## Les trois métriques CWV (2026)

| Métrique | Seuils officiels Google |
|----------|--------------------------|
| **INP** (Interaction to Next Paint) | Bon < 200ms / À améliorer 200-500ms / Mauvais > 500ms |
| **CLS** (Cumulative Layout Shift) | Bon < 0.1 / À améliorer 0.1-0.25 / Mauvais > 0.25 |
| **LCP** (Largest Contentful Paint) | Bon < 2.5s / À améliorer 2.5-4s / Mauvais > 4s |

**Note historique** : INP a remplacé FID (First Input Delay) en mars 2024 comme Core Web Vital officiel.

## Comment le menu impacte chaque métrique

### INP — Interaction to Next Paint

Le menu est une zone d'interaction critique (clic hamburger, hover dropdown). Chaque interaction doit rendre un nouveau frame en < 200ms.

**Patterns menu qui dégradent INP :**

1. **JS lourd au toggle du hamburger**
   - Calcul de hauteur du menu au clic (`element.scrollHeight`) → reflow coûteux
   - Animations `height: 0 → auto` (impossibles en CSS, obligent JS) → reflow/repaint

2. **Event listeners en cascade**
   - Un `mouseover` sur chaque `<li>` avec sous-menu → N listeners
   - Préférer un seul listener délégué

3. **Menus qui fetchent au hover/clic**
   - `fetch('/api/menu-items')` au premier hover → latence réseau ajoutée à l'INP
   - Préférer des menus préchargés dans le HTML

4. **Animations sur `width`, `height`, `top`, `left`**
   - Ces propriétés déclenchent layout + paint + composite
   - Préférer `transform` et `opacity` (composite seulement)

→ **Codes** : `HEAVY_JS_ON_TOGGLE`, `FETCH_ON_HOVER`, `NON_COMPOSITE_ANIMATION`

### CLS — Cumulative Layout Shift

Le CLS mesure les décalages visuels involontaires pendant la vie de la page.

**Patterns menu qui dégradent CLS :**

1. **Menu sticky sans padding réservé**
   - Menu initial en position statique, devient `position: fixed` au scroll
   - Moment de la transition : le contenu saute vers le haut
   - Solution : `padding-top` sur body dès le départ, égal à la hauteur du menu

2. **Images dans le menu sans dimensions**
   - Mega menu avec images produits sans `width` / `height` attributes
   - Les images se chargent et poussent le contenu en dessous
   - Solution : toujours `width` + `height` HTML + `aspect-ratio` CSS

3. **Fonts webfonts (FOUT/FOIT)**
   - Font système affichée d'abord, puis font custom charge et change la taille du menu
   - Solution : `font-display: swap` + dimensions similaires entre fallback et webfont

4. **Bannières au-dessus du menu**
   - Cookie banner, announcement bar qui s'injectent après chargement
   - Poussent tout le nav vers le bas → CLS catastrophique
   - Solution : réserver l'espace en CSS OU afficher avant tout autre contenu OU à la fin du body

5. **Menu avec image hero chargée en arrière-plan**
   - Si l'image devient le LCP et n'est pas préchargée, CLS possible quand elle apparaît

→ **Codes** : `MENU_IMAGES_WITHOUT_DIMENSIONS`, `STICKY_NAV_CLS_RISK`, `FONT_FOUT_RISK`, `BANNER_CLS_RISK`

### LCP — Largest Contentful Paint

Le LCP mesure quand le plus gros élément visible est rendu.

**Patterns menu qui dégradent LCP :**

1. **CSS du menu render-blocking**
   - `<link rel="stylesheet" href="menu.css">` dans `<head>` sans `media="print" onload` ou `preload`
   - Le navigateur doit parser ce CSS avant de peindre quoi que ce soit
   - Solution : inline le CSS critique du menu, lazy load le reste

2. **JS du menu render-blocking**
   - `<script src="menu.js">` synchrone dans `<head>`
   - Bloque le parsing HTML jusqu'à son téléchargement + exécution
   - Solution : `defer` ou `async`, ou placer juste avant `</body>`

3. **Menu est le LCP element**
   - Si le mega menu contient une grosse image hero et que c'est le plus grand élément visible
   - Dans ce cas : précharger l'image (`<link rel="preload" as="image">`)

4. **Fonts custom chargées pour le menu**
   - Font custom utilisée UNIQUEMENT dans le menu = chargement pour rien
   - Solution : `font-display: swap` + sous-ensemble de caractères

→ **Codes** : `RENDER_BLOCKING_MENU_CSS`, `RENDER_BLOCKING_MENU_JS`, `HEAVY_CUSTOM_FONT_IN_NAV`

## Détection statique vs mesure réelle

### Ce qu'on PEUT détecter dans un audit statique

- Poids du HTML du menu (octets)
- Nombre et taille des `<script>` liés au menu
- Présence de `defer`/`async` sur les scripts
- `<link rel="stylesheet">` render-blocking
- Images sans `width`/`height` dans le menu
- Patterns `position: sticky` / `fixed` dans le CSS fourni
- Usage de `transform`/`opacity` vs `width`/`height` dans le CSS

### Ce qu'on ne PEUT PAS sans mesure live

- Valeur réelle de INP / CLS / LCP
- Durée réelle du JS menu
- Impact du cache navigateur
- Comportement sur connexion 3G / 4G
- Percentile utilisateur (p75, p95)

→ **Toujours recommander** : Lighthouse Mobile + PageSpeed Insights + CrUX data GSC

## Poids HTML du menu

Convention pratique :

| Ratio HTML menu / HTML total | Verdict |
|------------------------------|---------|
| < 10% | OK |
| 10-20% | Acceptable |
| 20-40% | ATTENTION — menu lourd |
| > 40% | CRITIQUE — le menu mange le budget HTML |

Logique : un mega menu qui pèse 50% du HTML de chaque page = overhead énorme pour Googlebot et pour le rendu initial.

→ **Code `HEAVY_MENU_HTML_WEIGHT`** : IMPORTANT si > 20%, CRITIQUE si > 40%.

## Format finding

```json
{
  "severity": "important",
  "dimension": "performance_cwv",
  "code": "MENU_IMAGES_WITHOUT_DIMENSIONS",
  "message": "5 images dans le mega menu n'ont pas d'attributs width/height",
  "detail": "Sans dimensions explicites, ces images provoqueront du CLS au chargement (Cumulative Layout Shift > 0.1 = au-dessus du seuil 'Bon' défini par Google Web.dev). Ajouter width et height en attributs HTML, et aspect-ratio en CSS.",
  "evidence": "<img src='/mega-menu/cat1.jpg'> (5 occurrences sans dimensions)"
}
```
