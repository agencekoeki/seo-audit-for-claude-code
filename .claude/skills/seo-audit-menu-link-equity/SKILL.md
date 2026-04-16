---
name: seo-audit-menu-link-equity
description: Expertise maillage interne et distribution de PageRank. Brevets Google (Reasonable Surfer, Boilerplate Detection), First Link Priority, seuils quantitatifs. Utilisé par l'agent seo-audit-menu-link-equity.
---

# Skill : Expertise maillage interne

## Workflow

1. Lire le parsing JSON (via `seo-audit-menu-parser`)
2. Appliquer les règles de `references/`
3. Produire findings structurés

## Références

- `references/reasonable_surfer.md` — Brevet Google US 7,716,225 / US 9,305,099 (Reasonable Surfer Model)
- `references/boilerplate_patent.md` — Brevet Google US 8,898,296 (Boilerplate Detection)
- `references/first_link_priority.md` — Matt Cutts (2009), John Mueller (2021)
- `references/quantitative_thresholds.md` — Seuils communautaires qualifiés

## Dimensions à vérifier

1. Inventaire quantitatif (nombre liens, top-level, ratio)
2. Dilution d'équité (seuils Reasonable Surfer)
3. First Link Priority (ancres du menu = premières vues par Google)
4. Qualité des ancres (descriptives vs génériques)
5. Duplications inter-zones (header + footer pour même URL)
6. Cohérence thématique (Reasonable Surfer — pertinence contextuelle)
7. Pages stratégiques absentes

## Format de sortie JSON

Standard — voir CLAUDE.md projet.
