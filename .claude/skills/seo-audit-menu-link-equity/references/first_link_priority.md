# First Link Priority

## Origine du concept

### Matt Cutts (2009)

Dans une vidéo de 2009 devenue célèbre, Matt Cutts (alors head of webspam chez Google) explique :
> "If we're looking at a page with several links on it, we'll give more weight to the first link's anchor text."

La théorie : si une même URL est pointée plusieurs fois depuis une même page, Google ne retient pour le ranking que l'ancre du PREMIER lien dans le DOM.

Vidéo : https://www.youtube.com/watch?v=ofhwPC-5Ub4 (ref historique)

### John Mueller (2021) — confirmation partielle

> "We do look at the first link, we do focus on the first link. But we also do understand multiple links to the same page."
> — John Mueller, Google Search Central hangout, 2021

Mueller nuance : Google COMPREND les liens multiples, mais dans beaucoup de cas le premier a un poids particulier.

## Ce que ça change pour les menus

### Cas 1 — Duplication nav / footer

Le menu principal est souvent répété en haut du DOM, le footer en bas. Si les deux contiennent un lien vers `/contact`, le lien du menu principal (apparaît en premier dans le DOM) prend le dessus pour l'ancre.

**Conséquence pratique :**
- Si menu dit "Nous contacter" et footer dit "Contact client 24/7" → Google retient "Nous contacter" pour la page /contact
- Optimiser l'ancre du menu, pas celle du footer (pour les URLs dupliquées)

### Cas 2 — Logo + menu

Quasi tous les sites ont un `<a href="/">` sur le logo, qui apparaît AVANT les liens du menu. Problème : l'ancre du logo est souvent vide (juste une image) ou `<img alt="Nom de l'entreprise">`.

**Conséquence :**
- La homepage reçoit souvent comme "première ancre" le `alt` du logo, pas "Accueil" ni le mot-clé brand
- → Vérifier que le `alt` du logo est le nom de marque ("Kōeki Agency"), pas vide

### Cas 3 — Skip links

Un `<a href="#main-content" class="skip-link">Aller au contenu</a>` en début de body apparaît AVANT le menu dans le DOM.

**Conséquence :**
- Ce lien pointe vers `#main-content` (ancre interne), pas vers une URL → pas de souci pour l'équité des URLs externes
- Mais si le skip link est mal configuré et pointe vers une vraie URL → peut créer du bruit

## Ce que le principe NE dit PAS

- Il ne dit pas que Google IGNORE le deuxième lien — juste que le premier a plus de poids
- Il ne dit pas que c'est une pénalité
- Il ne dit pas de chiffre précis ("le premier lien = 80% du poids")
- Il ne dit pas que ça s'applique à TOUS les cas (Mueller a nuancé)

**→ Règle de rigueur** : formuler comme "tendance documentée par Matt Cutts (2009) et confirmée partiellement par John Mueller (2021)", pas comme "loi absolue".

## Audit : quoi vérifier

1. **Logo** : a-t-il un `alt` descriptif (nom de marque) ?
2. **Skip link** : si présent, ne crée-t-il pas de bruit sémantique ?
3. **Duplication menu/footer** : même URL a-t-elle la même ancre aux deux endroits ? (si non, noter laquelle gagne)
4. **Premier lien du `<nav>` principal** : l'ancre est-elle optimisée pour la page cible ?

## Exemples de findings

✅ **JE SAIS** : "Le logo pointe vers `/` avec `<img alt="">`. Le lien suivant dans le DOM est le menu 'Accueil' vers `/`."

✅ **JE PENSE** : "La première ancre de la homepage vue par Google est probablement vide (alt du logo). Selon la théorie First Link Priority (Matt Cutts 2009, John Mueller 2021), c'est cette ancre qui compte prioritairement. Recommandation : ajouter `alt='Kōeki Agency — Agence SEO'` sur le logo."

✅ **JE NE PEUX PAS VÉRIFIER** : "Le poids exact appliqué par Google au premier lien (non documenté publiquement)."
