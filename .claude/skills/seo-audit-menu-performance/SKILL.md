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

## Script disponible (v0.3)

**Directive d'appel.** L'agent DOIT appeler ce script en desktop ET en mobile sur chaque page auditée et inclure les résultats dans son JSON de findings (`audits/{AUDIT_ID}/findings/performance.json`).

### `scripts/performance_checks.js` — mesures CWV réelles via Playwright
**DOIT** être appelé en desktop ET en mobile. Instrumente PerformanceObserver pour capturer LCP, CLS, FCP, TTFB. Simule des interactions sans navigation (burger, scroll) pour mesurer INP. Seules les mesures PerformanceObserver comptent pour INP (`inp_p95_ms: null` si aucune mesure PO disponible). Mesure l'occupation du header sticky.
```bash
node performance_checks.js --url URL --output results.json [--viewport desktop|mobile] [--profile-dir PATH]
```
Items checklist v0.3 : **4.1.1, 4.2.1, 4.2.3, 4.3.1**

### `scripts/interstitial_checker.js` — interstitiels intrusifs mobile
**DOIT** être appelé sur chaque page auditée en viewport mobile. Détecte les éléments fixed/absolute couvrant >30% du viewport (hors header/nav). Qualifie les cookie banners comme non-intrusifs.
```bash
node interstitial_checker.js --url URL --output results.json [--profile-dir PATH]
```

Seuils appliqués : LCP ≤ 2500ms GOOD, CLS ≤ 0.1 GOOD, INP ≤ 200ms GOOD.

## Limites

Avec le script v0.3, les métriques CWV sont maintenant mesurées en synthétique. Restent comme limites :
- Les mesures sont synthétiques (lab data), pas des données terrain (field data CrUX)
- L'INP est estimé sur 2-3 interactions simulées, pas sur une session utilisateur complète
- Pour les données terrain, recommander Chrome UX Report ou PageSpeed Insights

## Format de sortie JSON

Standard. Voir CLAUDE.md projet.
