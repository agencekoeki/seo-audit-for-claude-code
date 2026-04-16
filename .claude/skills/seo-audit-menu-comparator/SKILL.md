---
name: seo-audit-menu-comparator
description: Comparaison d'un menu avant/après pour valider une refonte. Diff structurel entre deux versions parsées : URLs ajoutées/supprimées/modifiées, changements de profondeur, shifts d'ancres, changements sémantiques. Utilisé par l'orchestrateur en mode comparaison.
---

# Skill : Comparateur avant/après

## Workflow

Utilisé uniquement en mode COMPARAISON. L'orchestrateur a lancé deux audits en parallèle (AVANT et APRÈS) et demande maintenant un diff structuré.

1. Lire les deux parsings JSON (AVANT et APRÈS)
2. Lancer le script `scripts/compare_menus.py`
3. Produire un JSON de diff structuré
4. Flagger les changements risqués : URLs supprimées, ancres modifiées, profondeur accrue

## Script

**`scripts/compare_menus.py`** — compare deux JSON parsés issus de `seo-audit-menu-parser`.

### Utilisation

```bash
python3 .claude/skills/seo-audit-menu-comparator/scripts/compare_menus.py \
  --before audits/{AUDIT_ID}/findings/parsed-before.json \
  --after audits/{AUDIT_ID}/findings/parsed-after.json \
  --output audits/{AUDIT_ID}/findings/comparison.json
```

### Ce qu'il détecte

**URLs :**
- URLs AJOUTÉES (dans après, pas dans avant) — à vérifier qu'elles pointent vers des pages existantes
- URLs SUPPRIMÉES (dans avant, pas dans après) — **risque d'orphelin SEO** 🚨
- URLs MODIFIÉES (URL changée mais ancre identique) — peut indiquer une redirection

**Ancres :**
- Mêmes URLs mais ancres différentes → changement de signal SEO
- Ancres vidées → possible perte d'optimisation

**Structure :**
- Changement du nombre d'items top-level
- Changement de profondeur (niveaux d'imbrication)
- Changement du nombre de `<nav>`

**Sémantique :**
- Disparition de `<nav>` / `<main>` / `<header>` / `<footer>`
- Changement d'`aria-label`
- Apparition de patterns régressifs (div onclick, javascript: href)

## Règles d'alerte

| Changement détecté | Sévérité | Raison |
|--------------------|----------|--------|
| URL supprimée pointant vers page qui existe toujours | 🚫 BLOQUANT | Page orpheline créée |
| URL supprimée pointant vers 404 | 💡 Info | Normal si la page est vraiment supprimée |
| Ancre modifiée (même URL) | ⚠️ IMPORTANT | Changement de signal SEO |
| Profondeur augmentée pour pages stratégiques | 🔴 CRITIQUE | Viole la règle des 3 clics |
| Suppression d'`aria-label` sur `<nav>` | ⚠️ IMPORTANT | Régression accessibilité |
| Apparition de div onclick comme lien | 🚫 BLOQUANT | Régression crawlabilité |
| Nombre de liens top-level multiplié par > 2 | ⚠️ IMPORTANT | Risque de surcharge cognitive |
| Nombre de liens total divisé par > 2 | 🔴 CRITIQUE | Perte potentielle d'équité sur pages supprimées |

## Format de sortie JSON

```json
{
  "meta": {
    "compared_at": "ISO",
    "before_label": "Menu actuel en prod",
    "after_label": "Nouveau menu en staging"
  },
  "url_diff": {
    "added": ["/new-page", "/new-category"],
    "removed": ["/removed-page", "/old-section"],
    "kept": ["/contact", "/services", ...],
    "total_before": 45,
    "total_after": 32,
    "net_change": -13
  },
  "anchor_changes": [
    {
      "url": "/services",
      "before": "Nos services",
      "after": "Services"
    }
  ],
  "depth_changes": [
    {
      "url": "/tarifs",
      "before_depth": 1,
      "after_depth": 3,
      "impact": "Page stratégique enterrée plus profond"
    }
  ],
  "semantic_regressions": [
    {
      "type": "aria_label_removed",
      "detail": "<nav> principal : aria-label supprimé"
    }
  ],
  "issues": [
    {
      "severity": "bloquant",
      "dimension": "comparison",
      "code": "URLS_REMOVED_FROM_NAV",
      "message": "13 URLs supprimées du menu",
      "detail": "Ces pages ne reçoivent plus d'équité depuis la homepage. Risque d'orphelinage. Vérifier que chacune est soit redirigée (301), soit encore liée depuis d'autres pages.",
      "evidence": ["/old-section", "/removed-page", ...]
    }
  ],
  "verdict": "BLOQUANT|CRITIQUE|ATTENTION|OK",
  "summary_for_reporter": "Le nouveau menu supprime 13 URLs dont 8 pointent vers des pages qui existent toujours..."
}
```

## Limites (JE NE PEUX PAS VÉRIFIER)

- Savoir si les URLs supprimées sont vraiment supprimées côté serveur (nécessite crawl complet)
- Impact réel sur le trafic organique (nécessite monitoring GSC post-déploiement)
- Si les redirections 301 sont en place (nécessite test HTTP sur chaque URL supprimée)

→ Toujours recommander : tester chaque URL supprimée avec curl/Screaming Frog pour vérifier qu'elle retourne 200 ou 301 vers une page valide.
