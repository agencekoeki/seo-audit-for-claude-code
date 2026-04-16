# Boilerplate Detection — brevet Google

## Source primaire

- **US Patent 8,898,296** — "Detection of boilerplate content"
  - Inventeur : Andrey Fedorov
  - Assigné à : Google Inc.
  - Accordé : 25 novembre 2014
  - URL : https://patents.google.com/patent/US8898296B2/en

## Principe

Google identifie automatiquement les sections répétitives d'un site (menu, footer, sidebar, CTA récurrents) et leur applique un traitement différent du contenu principal.

Citation du brevet :
> "Boilerplate content typically includes navigation links, legal notices, copyright information, advertisements, and other content that is repeated across many pages of a website."

## Comment Google détecte le boilerplate

Méthodes combinées décrites dans le brevet :
1. **Détection de répétition cross-page** : un bloc présent quasi identique sur > N pages d'un domaine
2. **Analyse de templates** : identification des patterns HTML structurels répétés
3. **Heuristiques de position** : header/footer/sidebar ont une probabilité élevée d'être boilerplate
4. **Classification sémantique** : éléments `<header>`, `<nav>`, `<footer>`, `<aside>` suggérés comme boilerplate

## Impact sur les menus de navigation

### Les liens du menu sont classés boilerplate

Google sait qu'un menu répété sur toutes les pages est du boilerplate. Conséquence documentée :
- Le score de pertinence des mots-clés dans le menu est **ajusté à la baisse**
- Le poids des liens internes du menu est réduit vs des liens contextuels
- Le texte d'ancre du menu compte moins pour le ranking de la page cible qu'un lien contextuel avec la même ancre

Citation Martin Splitt (Google Search Relations) :
> "We try to understand which parts of a page are boilerplate and which are the main content. The main content matters more for ranking."
> — Google Search Central Office Hours, 2022

### Ce que ça change pour l'audit

**Implication 1 — Ne pas stuffer le menu de mots-clés**

Mettre "SEO Paris | SEO Agency | SEO Consultant | SEO Services" dans 4 items de menu = gaspillage. Google identifie le boilerplate et n'y accorde pas de poids exceptionnel.

→ **Règle d'audit** : flagger les menus avec répétition suspecte de mots-clés (code `KEYWORD_STUFFING_IN_NAV`) comme **IMPORTANT**.

**Implication 2 — Le contenu unique de chaque page est plus important**

Le H1, le contenu principal, les liens contextuels comptent bien plus que le menu pour le ranking.

→ **Règle d'audit** : si l'utilisateur demande "comment ranker la page X", ne pas juste suggérer d'ajouter un lien au menu — recommander aussi des liens contextuels depuis le contenu d'autres pages.

**Implication 3 — Les balises sémantiques AIDENT Google à identifier le boilerplate**

Contre-intuitif mais vrai : utiliser `<header>`, `<nav>`, `<footer>` ne "cache" pas le menu, ça aide Google à comprendre que c'est du boilerplate. C'est attendu et normal.

→ **Règle d'audit** : ne PAS recommander de "cacher" le menu pour tromper Google — ça ne marche pas.

## Limites à reconnaître

Le brevet décrit une méthode, pas l'algorithme en production. On sait que Google fait **quelque chose comme ça**, mais :
- Les seuils précis de détection sont inconnus
- La pondération exacte appliquée au boilerplate est inconnue
- Le brevet peut ne pas refléter l'état actuel de Google

**→ Règle de rigueur** : dans le rapport, écrire "selon le brevet Google US 8,898,296, les menus sont typiquement identifiés comme boilerplate et leur poids ajusté à la baisse" — jamais "Google pénalise les mots-clés dans le menu".

## Exemples de findings

✅ **JE SAIS** : "Les 12 items du menu top-level contiennent tous le mot 'SEO' dans leur ancre."

✅ **JE PENSE** : "Cette répétition est probablement identifiée comme boilerplate par Google (brevet US 8,898,296) et n'apporte pas de boost de ranking. L'effort serait mieux placé sur des liens contextuels depuis le contenu des articles du blog."

✅ **JE NE PEUX PAS VÉRIFIER** : "L'impact exact sur le ranking (dépend de l'algorithme live Google, non documenté publiquement)."
