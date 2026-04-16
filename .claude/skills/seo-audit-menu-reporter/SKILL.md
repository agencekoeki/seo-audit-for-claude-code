---
name: seo-audit-menu-reporter
description: Rédaction du rapport client final à partir des findings des spécialistes. Génération Markdown + HTML autonome. Applique la structure standardisée et la distinction SAVOIR/PENSER/PAS VÉRIFIER. Utilisé par les agents reporter et reviewer.
---

# Skill : Génération de rapport

## Workflow

1. Lire l'intake et tous les findings JSON (`audits/{AUDIT_ID}/findings/*.json`)
2. Lire la consolidation éventuelle faite par l'orchestrateur
3. Produire le rapport MD via le script `scripts/assemble_report.py`
4. Convertir en HTML via `scripts/md_to_html.py`
5. Déposer dans `audits/{AUDIT_ID}/reports/`

## Scripts

### `scripts/assemble_report.py`

Agrège les JSON de findings en un Markdown structuré selon le template.

### `scripts/md_to_html.py`

Convertit le Markdown en HTML autonome (CSS embarqué, pas de CDN), prêt à envoyer au client.

## Template de rapport

Structure obligatoire (voir `references/report_template.md`) :

1. En-tête (site, date, mode)
2. Synthèse exécutive (3-5 lignes)
3. Tableau de bord (matrix des 6 dimensions × verdicts)
4. Problèmes identifiés (par sévérité : BLOQUANTS, CRITIQUES, IMPORTANTS, RECOMMANDATIONS)
5. [Si mode COMPARAISON] Analyse différentielle
6. Méthodologie : JE SAIS / JE PENSE / JE NE PEUX PAS VÉRIFIER
7. Prochaines étapes recommandées
8. Annexes (inventaire URLs, sources citées)

## Règles éditoriales

- Phrases courtes
- Pas de jargon non expliqué
- Chiffres précis, pas "beaucoup"
- Sources inline (ex: "selon brevet Google US 7,716,225")
- Pas de flagornerie client
- Emojis limités aux titres de sévérité (🚫🔴⚠️💡)
- Recommandations concrètes et actionnables
