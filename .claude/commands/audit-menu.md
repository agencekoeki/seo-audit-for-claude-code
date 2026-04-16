---
description: Lance un audit SEO complet de menu de navigation, en mode audit simple ou comparaison avant/après
argument-hint: "[mode: audit|compare] [url optionnelle]"
---

# /audit-menu — Orchestrateur d'audit de menu de navigation

Tu es le **point d'entrée** d'un audit SEO de menu de navigation. Ton rôle est d'invoquer l'agent `seo-audit-menu-orchestrator` qui va mener l'audit de bout en bout.

## Arguments passés par l'utilisateur

$ARGUMENTS

## Ton travail

1. Invoque l'agent `seo-audit-menu-orchestrator` via le Task tool
2. Passe-lui les arguments fournis par l'utilisateur (s'il y en a)
3. Laisse-le gérer l'intégralité de l'audit

**NE FAIS PAS** l'audit toi-même. Tu es juste le pont vers l'orchestrateur. L'orchestrateur sait comment interviewer l'utilisateur, dispatcher le travail aux spécialistes, consolider, et livrer le rapport.

## Invocation

```
Task(
  subagent_type="seo-audit-menu-orchestrator",
  description="Audit SEO de menu de navigation",
  prompt="L'utilisateur a lancé /audit-menu avec les arguments suivants : {$ARGUMENTS}. Prends en charge l'audit de A à Z : interview maïeutique, collecte des pages, dispatch aux spécialistes, consolidation, rédaction du rapport, review QA, livraison finale."
)
```

Si les arguments sont vides, laisse quand même l'orchestrateur démarrer — il sait poser les bonnes questions.
