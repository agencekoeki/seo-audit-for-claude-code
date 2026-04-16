---
name: seo-audit-menu-performance
description: Expertise Core Web Vitals appliqués aux menus. INP, CLS, LCP et les patterns de menu qui les dégradent. Utilisé par l'agent seo-audit-menu-performance.
---

# Skill : Performance et Core Web Vitals

## Workflow

1. Lire le HTML source et le CSS fourni (si disponible)
2. Rechercher les patterns à risque CWV
3. Si l'utilisateur a fourni un rapport Lighthouse/PageSpeed JSON : extraire les métriques réelles
4. Produire findings avec distinction JE SAIS / JE PENSE / JE NE PEUX PAS VÉRIFIER

## Référence

`references/cwv_thresholds.md` — seuils Google officiels et patterns menu qui dégradent chaque métrique

## Limites

La plupart des findings CWV nécessitent une mesure réelle en conditions utilisateur. En audit statique :
- On peut détecter les PATTERNS À RISQUE (evidence-based)
- On ne peut PAS mesurer les métriques réelles
- Toujours recommander un Lighthouse / PageSpeed Insights en complément

## Format de sortie JSON

Standard. Voir CLAUDE.md projet.
