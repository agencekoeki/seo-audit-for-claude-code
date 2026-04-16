# Mobile-first indexing et navigations mobiles

## Source primaire

- Google Search Central : Mobile-first indexing best practices
- Historique : annoncé 2016, généralisé fin 2020, par défaut pour tous nouveaux sites depuis 2023

## Principe

Google utilise la version **MOBILE** de chaque site pour l'indexation et le ranking. La version desktop est ignorée pour le ranking (sauf exceptions rares).

Conséquence critique : si un lien n'apparaît QUE dans la version desktop, **Google ne le voit pas pour le ranking**.

## Implications pour les menus

### Cas 1 — Menu identique desktop/mobile (idéal)

Le hamburger menu mobile contient exactement les mêmes URLs que le menu desktop. Tous les liens sont dans le DOM initial (présents dans le HTML, juste cachés via CSS).

→ **OK**, aucune perte d'équité.

### Cas 2 — Menu mobile réduit

Version desktop : 40 items top-level visibles.
Version mobile : 8 items principaux, les 32 autres en "footer menu" ou cachés.

→ **CRITIQUE** : 32 URLs perdues pour le ranking. Ces pages sont indexées indirectement (sitemap, autres pages) mais ne reçoivent plus d'équité de la homepage.

→ **Code `MOBILE_MENU_MISSING_LINKS`**.

### Cas 3 — Menu mobile généré par JS au clic

Le hamburger button déclenche au clic un appel `fetch()` pour charger les items du menu. Le DOM initial (ce que Googlebot voit) ne contient QUE le bouton, pas les liens.

→ **BLOQUANT** : menu invisible à Googlebot.

→ **Code `MOBILE_MENU_JS_INJECTED`**.

### Cas 4 — Menu desktop affiché, menu mobile caché via `display: none`

```css
@media (max-width: 768px) {
  .main-nav { display: none; }
}
```

Si la nav est `display:none` en mobile SANS remplacement visible → les utilisateurs mobiles n'ont pas de menu ET Googlebot mobile ne l'affiche pas non plus.

→ **BLOQUANT** si aucun menu alternatif mobile détectable.

Si remplacement par un hamburger → vérifier que le hamburger a bien les liens dans le DOM initial.

### Cas 5 — Détection via CSS inline fourni

Si le CSS est fourni (dans `<style>` inline ou `<link>` local) :
- Chercher `@media (max-width: ...)` avec `display: none` sur les sélecteurs de nav
- Flagger si `display: none` sans alternative mobile détectable

## Pattern hamburger correct

```html
<nav aria-label="Navigation principale">
  <button 
    aria-expanded="false" 
    aria-controls="main-menu"
    class="hamburger-toggle">
    <span class="sr-only">Menu</span>
    <!-- icône hamburger -->
  </button>
  
  <ul id="main-menu" class="main-menu">
    <li><a href="/services">Services</a></li>
    <li><a href="/produits">Produits</a></li>
    <li><a href="/contact">Contact</a></li>
    <!-- ... tous les liens dans le DOM initial -->
  </ul>
</nav>
```

```css
/* Mobile : cache visuellement mais liens restent dans le DOM */
@media (max-width: 768px) {
  .main-menu {
    display: none;
  }
  .main-menu[aria-expanded="true"] {
    display: block;
  }
}
```

Points clés :
- Tous les `<a href>` sont dans le HTML initial
- `display: none` cache visuellement mais **n'empêche PAS Googlebot de voir les liens**
- `aria-expanded` mis à jour par JS au clic du bouton

## Pattern hamburger INCORRECT

```html
<button onclick="loadMenu()">Menu</button>
<div id="menu-container"></div>

<script>
function loadMenu() {
  fetch('/api/menu').then(r => r.json()).then(items => {
    // Injection AJAX des liens
  });
}
</script>
```

→ Les liens ne sont jamais dans le HTML servi. Googlebot ne voit rien.

## Test sans accès live

Ce qu'on peut vérifier en auditant le HTML source mobile (ou desktop avec User-Agent mobile) :

1. **Compter les `<a href>` dans `<nav>`** en desktop vs mobile → ratio doit être ≥ 95%
2. **Détecter les patterns `fetch()` / `XMLHttpRequest`** dans les scripts liés au menu
3. **Chercher dans le CSS** les media queries qui cachent le nav sans alternative

Ce qu'on NE peut PAS vérifier sans test live :
- Le comportement réel du hamburger au clic
- La taille des tap targets réellement rendus
- L'animation de transition

→ Flagger comme JE NE PEUX PAS VÉRIFIER et recommander Lighthouse Mobile.

## Outils live recommandés

À suggérer dans le rapport :
- **Lighthouse Mobile** (Chrome DevTools → Lighthouse → Mobile) : audit complet accessibility + performance
- **Chrome DevTools → Device Mode** : simuler un mobile, vérifier que le hamburger fonctionne
- **Mobile-Friendly Test Google** (déprécié fin 2023, mais Rich Results Test fonctionne encore)
- **Page Experience Report dans GSC** : vérifier qu'il n'y a pas d'erreurs mobile

## Format finding

```json
{
  "severity": "critique",
  "dimension": "mobile_first",
  "code": "MOBILE_MENU_MISSING_LINKS",
  "message": "Version mobile affiche 8 liens dans le menu, version desktop 40",
  "detail": "Google indexe la version mobile (mobile-first indexing). Les 32 liens uniquement présents en desktop ne contribuent pas à l'équité interne. Solution : inclure tous les liens dans le DOM mobile, quitte à les afficher dans un hamburger multi-niveaux.",
  "evidence": "Desktop: 40 <a href> dans .main-nav / Mobile: 8 <a href> dans .main-nav"
}
```
