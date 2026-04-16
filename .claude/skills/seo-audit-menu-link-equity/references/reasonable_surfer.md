# Reasonable Surfer Model — brevet Google

## Sources primaires

- **US Patent 7,716,225** — "Ranking documents based on user behavior and/or feature data"
  - Inventeurs : Jeffrey A. Dean, Corin Anderson, Alexis Battle
  - Assigné à : Google Inc.
  - Accordé : 11 mai 2010
  - Filé : 17 juin 2004
  - URL : https://patents.google.com/patent/US7716225B1/en

- **US Patent 9,305,099** — Continuation / mise à jour
  - Accordé : 5 avril 2016
  - Filé : 10 janvier 2012
  - URL : https://patents.google.com/patent/US9305099B1/en

- **Décryptage référence** : Bill Slawski (†2022), "SEO by the Sea"
  - https://www.seobythesea.com/2010/05/googles-reasonable-surfer-how-the-value-of-a-link-may-differ-based-upon-link-and-document-features-and-user-data/
  - https://www.seobythesea.com/2016/04/googles-reasonable-surfer-patent-updated/

## Principe fondamental

Contrairement au modèle "Random Surfer" originel (Brin & Page, 1998) où chaque lien d'une page distribuait le PageRank de manière égale, le Reasonable Surfer Model pondère chaque lien selon la **probabilité qu'un utilisateur raisonnable le clique**.

Citation du brevet :
> "This reasonable surfer model reflects that not all the links associated with a document are equally likely to connect. Examples of unlikely followed links may include 'Terms of Service' links, banner advertisements, and links unrelated to the document."

## Facteurs de pondération identifiés dans le brevet

Les features qui influencent le poids d'un lien :
1. **Position sur la page** — above the fold vs below the fold
2. **Position dans le DOM** — contenu principal vs boilerplate
3. **Couleur/taille de la police** — liens visibles vs discrets
4. **Mise en forme** — gras, italique, souligné vs texte normal
5. **Ancres et texte du lien** — quantité de mots, pertinence
6. **Cohérence thématique** — lien source/cible sur le même sujet
7. **Taille du lien** — plus grand = plus susceptible d'être cliqué
8. **Position relative** — premier de la liste vs enterré
9. **Emphase visuelle** — couleur contrastée, bouton, icône
10. **Interaction utilisateur historique** — selection data (mise à jour 2016)

## Implications SEO pour les menus

### Implication 1 — Les liens de navigation ne valent pas les liens contextuels

Un lien dans le corps du contenu, entouré de texte pertinent, avec une ancre descriptive, transmet plus d'équité qu'un lien identique dans le menu global répété sur chaque page.

**→ Règle d'audit** : ne pas se reposer uniquement sur le menu pour promouvoir une page stratégique. Elle doit AUSSI être liée contextuellement depuis le contenu.

### Implication 2 — Dilution par la quantité

Plus il y a de liens dans le menu, moins chacun reçoit de poids. Le PageRank disponible est divisé.

**Seuils pratiques (consensus communautaire, pas brevet) :**
- < 25 liens dans la nav : OK
- 25-50 liens : attention, dilution modérée
- 50-100 liens : dilution importante
- > 100 liens : dilution sévère, signal de mauvaise architecture

**→ Règle d'audit** : flagger toute nav avec > 50 liens en **CRITIQUE**, > 100 en **BLOQUANT** (code `TOO_MANY_NAV_LINKS`).

### Implication 3 — Cohérence thématique des mega menus

Un mega menu qui liste des catégories non liées à la page actuelle transmet moins d'équité à chaque lien (thematic incoherence).

Exemple : sur une page "chaussures de running", le mega menu affiche aussi "ustensiles de cuisine", "jardinage", "électronique". Chaque lien est moins valorisé que sur une page de catégorie cohérente.

**→ Règle d'audit** : si l'utilisateur fournit plusieurs pages thématiquement différentes, vérifier que le mega menu est adapté à chaque contexte ou signaler l'incohérence comme **IMPORTANT**.

### Implication 4 — Footer links très dévalorisés

Les liens du footer sont explicitement cités dans le brevet comme ayant une faible probabilité de clic (comme les "Terms of Service"). Ils transmettent peu d'équité.

**→ Règle d'audit** : ne pas compter sur le footer pour promouvoir une page importante. Si une page stratégique n'est QUE dans le footer, flagger comme **CRITIQUE**.

## Mise à jour 2016 — intégration des données de sélection

Le brevet continuation (2016) ajoute :
> "the weight is determined based on the particular feature data and selection data, the selection data identifying user behavior relating to links to other documents"

Google utilise aussi les **données réelles de clics** pour pondérer les liens (pas juste des heuristiques de positionnement). Les liens effectivement cliqués par les utilisateurs reçoivent plus de poids.

**→ Implication d'audit** : les menus design pour le clic (CTA visibles, hiérarchie claire) sont favorisés par Google. Un menu où tout se ressemble dilue l'attention utilisateur → dilue l'équité perçue.

## Ce que le brevet NE dit PAS

Attention aux sur-interprétations communes :
- Le brevet ne dit pas que Google utilise ACTUELLEMENT ce modèle en production (c'est un brevet, pas une annonce de feature)
- Le brevet ne dit pas de seuils chiffrés (les "25, 50, 100" sont des conventions communautaires)
- Le brevet ne dit pas que les nav links valent "X% moins" que les liens contextuels (pas de chiffre précis)

**→ Règle de rigueur dans l'audit** : distinguer entre "brevet dit" (JE SAIS) et "interprétation communautaire" (JE PENSE). Ne jamais prêter à Google des règles qu'il n'a pas publiées.

## Exemples de findings corrects

✅ **JE SAIS** : "Le menu contient 87 liens top-level + sous-niveaux."

✅ **JE PENSE** : "Ce volume dépasse largement les seuils communautaires (50 liens = attention, 100 = sévère). Selon le modèle Reasonable Surfer décrit dans le brevet Google US 7,716,225, plus il y a de liens, moins chacun transmet d'équité. La page /tarifs, avec son anchor 'Tarifs', reçoit donc une part très faible du PageRank interne depuis la homepage."

✅ **JE NE PEUX PAS VÉRIFIER** : "La pondération exacte appliquée par Google en production (algorithme non public)."

❌ **Faux** : "Google pénalise les menus avec plus de 50 liens." (pas de pénalité, juste dilution)
❌ **Faux** : "Le brevet Reasonable Surfer est l'algorithme de Google." (c'est un brevet parmi des milliers)
