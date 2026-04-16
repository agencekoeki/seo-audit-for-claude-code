---
name: seo-audit-menu-architecture
description: Expertise information architecture et UX stratégique des menus. Hiérarchie logique, règle des 3 clics, pages stratégiques, parcours client, silos thématiques. Utilisé par l'agent seo-audit-menu-architecture.
---

# Skill : Architecture de l'information

## Workflow

1. Lire l'intake (contexte business, secteur, objectifs)
2. Lire le parsing JSON pour avoir la structure du menu
3. Si fourni : croiser avec sitemap.xml ou liste de pages stratégiques
4. Produire des findings orientés business/stratégie

## Dimensions à vérifier

1. **Hiérarchie logique** : les catégories top-level reflètent-elles le business model ?
2. **Règle des 3 clics** : pages stratégiques accessibles en ≤ 3 clics
3. **Breadcrumbs** : présents, cohérents avec le menu ?
4. **Pages parasites en top-level** : CGV / mentions légales en position proéminente = signal faible
5. **Parcours client** : un nouveau visiteur comprend-il ?
6. **Vocabulaire client vs interne** : labels adaptés ?
7. **CTA visible** : contact, devis, achat, selon le business model
8. **Cohérence avec business model** : e-commerce, SaaS, service pro, média...

## Spécificité de ce skill

Contrairement aux autres spécialistes qui vivent dans du HTML et des brevets, toi tu raisonnes en **langage client**. Tu peux être moins technique et plus stratégique.

Exemples de formulations valorisées :
- "Le menu donne l'impression d'un site corporate alors que c'est un e-commerce"
- "Enterrer /tarifs à 4 clics est incohérent avec un objectif de conversion"
- "`Blog` et `Actualités` coexistent — doublon à clarifier"

## Limites (JE NE PEUX PAS VÉRIFIER)

Sans données business :
- Quelles pages génèrent du trafic/conversions (nécessite GA4)
- Quels sont les mots-clés prioritaires (nécessite GSC / brief marketing)
- Le parcours utilisateur réel (nécessite analytics + heatmaps)

→ Toujours recommander : GA4 + Search Console + éventuellement Hotjar pour un audit complet.

## Format de sortie JSON

Standard. Les findings peuvent être moins "chiffrés" et plus "narratifs" que pour les autres spécialistes, mais doivent rester evidence-based (on cite ce qu'on voit dans le menu).
