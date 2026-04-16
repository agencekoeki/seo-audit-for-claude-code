# WCAG 2.1 / 2.2 appliqués aux menus de navigation

## Sources primaires

- WCAG 2.1 : https://www.w3.org/TR/WCAG21/
- WCAG 2.2 : https://www.w3.org/TR/WCAG22/ (publié octobre 2023)
- Quick reference : https://www.w3.org/WAI/WCAG21/quickref/
- ARIA Authoring Practices (menus) : https://www.w3.org/WAI/ARIA/apg/patterns/menubar/

## Critères applicables aux menus

### Niveau A (obligatoires légalement dans nombreuses juridictions)

#### 2.1.1 Keyboard (A)
**Critère** : "All functionality of the content is operable through a keyboard interface without requiring specific timings for individual keystrokes."

**Application menu** :
- Tous les items du menu doivent être atteignables via la touche Tab
- Les sous-menus doivent être ouvrables via Enter ou flèches
- Aucun clic souris obligatoire

**Test (nécessite live)** : JE NE PEUX PAS VÉRIFIER en audit statique
**Ce que je PEUX détecter** : usage de `tabindex="-1"` qui exclut du parcours clavier

#### 2.1.2 No Keyboard Trap (A)
**Critère** : Pouvoir sortir d'un composant avec Tab ou Escape.

**Application** : Les modals de menu mobile doivent permettre Escape pour fermer.

**Détection statique** : JE NE PEUX PAS VÉRIFIER complètement (nécessite test live).

#### 2.4.1 Bypass Blocks (A)
**Critère** : "A mechanism is available to bypass blocks of content that are repeated on multiple Web pages."

**Application** : skip link `<a href="#main-content" class="skip-link">Aller au contenu principal</a>` en début de `<body>`.

**Détection** : facile — présence ou absence d'un skip link en début de body.

→ **Code `MISSING_SKIP_LINK`** : IMPORTANT si absent.

#### 2.4.3 Focus Order (A)
**Critère** : L'ordre de focus au clavier doit être cohérent avec l'ordre logique et visuel.

**Détection** : difficile sans live testing. Flagger si `tabindex` positifs détectés (anti-pattern).

#### 4.1.2 Name, Role, Value (A)
**Critère** : Les composants UI doivent avoir nom + rôle + état programmatiquement accessibles.

**Application** :
- Toggles de sous-menus → `aria-expanded="true|false"`, mise à jour dynamique
- `<nav>` → rôle implicite `navigation`, ou `role="navigation"` sur un `<div>` (moins bien)
- Boutons → `<button aria-expanded>`, pas `<div>`

→ **Codes** : `TOGGLE_WITHOUT_ARIA_EXPANDED`, `NON_SEMANTIC_TOGGLE`.

### Niveau AA (recommandés, exigés pour secteur public en UE)

#### 2.4.6 Headings and Labels (AA)
**Critère** : Les labels décrivent clairement le sujet ou la fonction.

**Application** :
- `aria-label` sur chaque `<nav>` distinct ("Navigation principale", "Navigation footer")
- Ancres descriptives pour les liens

→ **Code `NAV_NO_ARIA_LABEL`** : IMPORTANT.

#### 2.4.7 Focus Visible (AA)
**Critère** : L'indicateur de focus clavier doit être visible.

**Application** : ne pas masquer le focus avec `outline: none` sans remplacement.

**Détection statique** : recherche de `outline: none` ou `outline: 0` dans le CSS fourni → flagger.

→ **Code `FOCUS_VISIBLE_DISABLED`** : CRITIQUE si détecté sans `:focus-visible` alternative.

#### 1.4.11 Non-text Contrast (AA)
**Critère** : Ratio de contraste ≥ 3:1 pour les éléments d'interface (boutons, icônes, bordures de focus).

**Détection statique** : difficile sans parsing CSS complet. Flagger comme JE NE PEUX PAS VÉRIFIER.

### Niveau AAA (idéal, mentionnés dans l'audit si pertinents)

#### 2.4.8 Location (AAA)
**Critère** : Information sur la localisation de l'utilisateur dans le site.

**Application** :
- `aria-current="page"` sur le lien actif
- Breadcrumbs

→ **Code `NO_ARIA_CURRENT`** : RECOMMANDATION (AAA, pas obligatoire).

## WCAG 2.2 — nouveautés spécifiques nav

Publié en octobre 2023, ajoute des critères pertinents pour les menus :

#### 2.4.11 Focus Not Obscured (Minimum) (AA — nouveau en 2.2)
**Critère** : Quand un élément a le focus clavier, il ne doit pas être entièrement caché par un autre élément (ex: sticky nav qui cache le contenu en scroll).

**Application** : les sticky nav ou les menus déroulants ne doivent pas cacher les éléments focus.

#### 2.5.8 Target Size (Minimum) (AA — nouveau en 2.2)
**Critère** : Les cibles interactives doivent faire au moins 24x24px (CSS pixels).

**Application** : les liens du menu mobile doivent respecter cette taille minimale.

**Note** : c'est moins strict que les recommandations iOS (44x44) et Material (48x48), mais c'est le minimum WCAG.

→ **Code `SMALL_TAP_TARGETS`** : IMPORTANT si CSS détectable indique < 24x24 sur mobile.

## Éléments ARIA pour les menus

### ARIA Authoring Practices — Menubar pattern

Pour un menu principal avec sous-menus :

```html
<nav aria-label="Navigation principale">
  <ul role="menubar">
    <li role="none">
      <a href="/services" role="menuitem" aria-current="page">Services</a>
    </li>
    <li role="none">
      <button 
        role="menuitem" 
        aria-haspopup="true" 
        aria-expanded="false"
        aria-controls="submenu-produits">
        Produits
      </button>
      <ul role="menu" id="submenu-produits" hidden>
        <li role="none">
          <a href="/produits/seo" role="menuitem">SEO</a>
        </li>
      </ul>
    </li>
  </ul>
</nav>
```

**Nuance importante** : `role="menubar"` et `role="menu"` activent des comportements clavier spécifiques (flèches directionnelles à la place de Tab). C'est plus complexe à implémenter correctement.

**Alternative plus simple** (acceptée) : ne pas utiliser `role="menubar"`, juste `<ul><li><a href>` avec aria-label sur le nav. Plus simple, Tab fonctionne nativement.

## Règle de rigueur dans l'audit

Dans le rapport, toujours :
- Citer le critère WCAG précis ("WCAG 2.4.6 niveau AA")
- Distinguer ce qu'on peut vérifier en statique vs ce qui nécessite du live
- Ne pas prétendre qu'un site est "WCAG compliant" sans tests live (axe, WAVE, Lighthouse, tests manuels clavier + lecteurs d'écran)

## Format finding

```json
{
  "severity": "critique",
  "dimension": "accessibility",
  "code": "MISSING_SKIP_LINK",
  "message": "Aucun skip link détecté",
  "detail": "WCAG 2.4.1 niveau A exige un mécanisme pour sauter les blocs répétés. Ajouter en début de <body> : <a href='#main-content' class='skip-link'>Aller au contenu</a>.",
  "evidence": "Premiers 500 caractères du <body> inspectés, aucun skip link détecté."
}
```
