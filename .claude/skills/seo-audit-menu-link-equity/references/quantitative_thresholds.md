# Seuils quantitatifs pour les menus de navigation

## Avertissement

Tous les seuils de ce document sont des **conventions communautaires qualifiées**, pas des chiffres officiels Google.

Google a historiquement communiqué des choses vagues ("keep it reasonable", "use common sense"). Les seuils ci-dessous sont issus de la pratique SEO, des analyses de cas publiés (Sitebulb, Screaming Frog, Ahrefs), et du bon sens.

**→ Dans tout rapport, formuler comme "selon les conventions communautaires" ou "sur la base des seuils observés empiriquement", jamais comme "selon Google".**

## Nombre total de liens dans le menu

### Seuils

| Nombre de liens | Verdict | Logique |
|-----------------|---------|---------|
| < 25 | OK | Structure claire, distribution d'équité correcte |
| 25-50 | ATTENTION | Commence à diluer, vérifier si tous sont nécessaires |
| 50-100 | CRITIQUE | Dilution significative (Reasonable Surfer), UX difficile |
| > 100 | BLOQUANT | Probable mega menu surchargé, repenser l'architecture |

### Origine des chiffres

- **~100 liens par page** était une vieille recommandation Google (2002-2008) pour le crawl budget. Abandonnée officiellement en 2014 (John Mueller : "we can handle more than 100 links"), mais reste un repère pragmatique.
- **50 liens** : seuil communautaire où la plupart des consultants commencent à flagger.
- **25 liens** : correspond à un menu principal classique (5-8 items top-level × 3-4 sous-items).

### Code finding

`TOO_MANY_NAV_LINKS` avec sévérité selon le bucket.

## Profondeur de navigation

### Règle des 3 clics

**Origine** : Jeffrey Zeldman, "Taking Your Talent to the Web" (2001). Popularisée par la pratique UX.

**Statut** : principe UX, pas règle SEO dure. Google ne pénalise pas directement la profondeur, mais :
- Plus une page est profonde, moins elle reçoit d'équité
- Une page à 5 clics de la homepage aura probablement un crawl et une indexation moins fréquents

### Seuils

| Depth from homepage | Verdict |
|--------------------|---------|
| 0-3 clics | OK pour les pages stratégiques |
| 4 clics | ATTENTION — justifiable si logique business |
| 5+ clics | CRITIQUE pour pages stratégiques |

### Code finding

`STRATEGIC_PAGE_TOO_DEEP` si une page listée comme stratégique dans l'intake nécessite > 3 clics.

## Items top-level du menu

### Seuils cognitifs

| Items top-level | Verdict | Logique |
|-----------------|---------|---------|
| 3-7 items | OK | Limite cognitive classique (Miller, 1956 — The Magical Number Seven) |
| 8-10 items | ATTENTION | Limite supérieure acceptable |
| 11-15 items | IMPORTANT | Difficile à scanner en une seconde |
| > 15 items | CRITIQUE | Signal de mauvaise architecture ou manque de priorisation |

### Référence

George A. Miller, "The Magical Number Seven, Plus or Minus Two", Psychological Review, 1956. Appliqué aux menus par la pratique UX moderne (NN/g, Luke Wroblewski).

### Code finding

`TOO_MANY_TOP_LEVEL_ITEMS` avec sévérité selon bucket.

## Ratio nav/total liens de la page

### Seuils

| Ratio liens nav / liens page | Verdict |
|------------------------------|---------|
| < 30% | OK (contenu prédomine) |
| 30-50% | ATTENTION |
| 50-70% | IMPORTANT (peu de liens contextuels dans le contenu) |
| > 70% | CRITIQUE (page pauvre en contenu, ou contenu sans maillage) |

### Logique

Si 70% des liens d'une page sont dans le menu, c'est que la page elle-même n'a quasi pas de liens contextuels. Problème de maillage interne sous-optimal — la page ne distribue pas d'équité vers d'autres pages via son contenu.

### Code finding

`NAV_DOMINATES_PAGE_LINKS` si ratio > 70%.

## Doublons d'URL dans le menu (même page)

| Doublons | Verdict |
|----------|---------|
| 0 | OK |
| 1-2 | ATTENTION — peut être justifié (CTA + menu) |
| 3+ | CRITIQUE — gaspillage évident d'équité |

### Code finding

`DUPLICATE_URLS_IN_NAV` pour chaque URL dupliquée > 2 fois.

## Profondeur du menu (niveaux d'imbrication)

| Niveaux (dans les `<ul>/<li>`) | Verdict |
|--------------------------------|---------|
| 1 niveau (menu plat) | OK pour petits sites |
| 2 niveaux | OK (standard mega menu) |
| 3 niveaux | ATTENTION — UX difficile, mobile très pénalisé |
| 4+ niveaux | BLOQUANT — quasi impossible à naviguer en mobile |

### Code finding

`NAV_TOO_DEEP` si > 3 niveaux.

## Case study — impact documenté

### Sitebulb (Dena Warren, août 2025)

Cas publié : refonte de menu sans audit préalable → **-70% de trafic organique en un mois**.

Cause : suppression d'items menu qui pointaient vers des pages de longue traîne bien rankées, créant de facto des pages orphelines (plus liées depuis le menu, plus d'équité transmise).

Leçon d'audit : **TOUJOURS valider une refonte de menu AVANT déploiement** avec le mode comparaison. Le diff avant/après identifie les URLs perdues.

Source : https://sitebulb.com/ (case study Dena Warren)

## Format dans le rapport

Toujours citer la source/origine du seuil utilisé. Exemple :

✅ "Le menu contient 87 liens top-level + sous-niveaux. Selon les seuils communautaires (> 50 liens = critique, cohérent avec le modèle Reasonable Surfer du brevet Google US 7,716,225), ce volume dilue significativement l'équité transmise à chaque lien."

❌ "Google pénalise les menus avec plus de 50 liens." — faux, non sourcé.
