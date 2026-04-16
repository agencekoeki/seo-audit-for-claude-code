# CLAUDE.md

Instructions pour Claude Code lorsqu'il travaille sur ce repository.

## Projet : seo-audit-for-claude-code

Toolkit d'audits SEO techniques en Python pur, piloté par Claude Code via un système d'**agents spécialisés + skills réutilisables**. Chaque audit est orchestré comme une équipe de consultants : un chef de projet maïeute, des spécialistes techniques, un rédacteur, un relecteur QA.

### Propriétaire
Sébastien Grillot — Kōeki Agency (Tarascon, France). SEO consultant + formateur IA.

## Architecture : agents + skills

Ce projet utilise la combinaison **subagents Claude Code + skills portables** :
- Les **agents** (`.claude/agents/`) sont des rôles métier avec leur propre contexte et leurs permissions d'outils
- Les **skills** (`.claude/skills/`) sont des expertises réutilisables chargées dans les agents via le champ `skills:` de leur frontmatter
- Un **slash command** (`.claude/commands/audit-menu.md`) est le point d'entrée utilisateur

### Les 10 rôles de l'équipe d'audit

**Coordination (3 rôles)**
1. `seo-audit-menu-orchestrator` — Chef de projet maïeute. Interview le client, dispatch le travail, assemble les retours.
2. `seo-audit-menu-reporter` — Rédacteur senior. Transforme les findings en rapport client livrable.
3. `seo-audit-menu-reviewer` — QA / avocat du diable. Challenge le rapport avant livraison.

**Spécialistes techniques (7 rôles)**
4. `seo-audit-menu-fetcher` — Collecteur de données. curl / Playwright MCP / fichiers locaux.
5. `seo-audit-menu-semantic` — Ingénieur front-end. HTML sémantique, ARIA, structure.
6. `seo-audit-menu-link-equity` — Analyste maillage interne. Brevets Google, distribution PageRank.
7. `seo-audit-menu-crawlability` — Expert crawl & rendering. HTML source vs DOM rendu, SPA, SSR.
8. `seo-audit-menu-accessibility` — Mobile-first & WCAG 2.1/2.2.
9. `seo-audit-menu-performance` — Core Web Vitals appliqués aux menus.
10. `seo-audit-menu-architecture` — Information architecture, parcours client, silos.

## Philosophie non-négociable

### 1. Maïeutique, pas CLI aveugle
L'orchestrateur POSE DES QUESTIONS avant de lancer quoi que ce soit. Il identifie le mode (audit vs comparaison), le périmètre, les données disponibles, les contraintes. Jamais de `python script.py URL` sans interview préalable.

### 2. Distinction obligatoire SAVOIR / PENSER / NE PEUX PAS VÉRIFIER
Tous les rapports distinguent explicitement :
- **JE SAIS** : fait vérifié dans les données fournies
- **JE PENSE** : interprétation basée sur une source documentée
- **JE NE PEUX PAS VÉRIFIER** : nécessite un accès live / données complémentaires

Cette règle s'applique à chaque agent, pas juste au rapport final.

### 3. Verdicts à 4 niveaux
🚫 BLOQUANT / 🔴 CRITIQUE / ⚠️ IMPORTANT / 💡 RECOMMANDATION. Jamais de score composite.

### 4. Zéro dépendance lourde côté Python
Python 3.10+ standard library. Playwright MCP pour le browser (externalisé, pas une dépendance Python).

### 5. Les scripts sont stupides mais honnêtes
Les scripts Python font UNE chose, la font bien, et **disent pourquoi quand ils échouent**. Codes de retour clairs, logs structurés sur stderr, JSON sur stdout. Jamais de "crash silencieux".

## Architecture de fichiers

```
seo-audit-for-claude-code/
├── CLAUDE.md                    ← Ce fichier
├── README.md                    ← Pitch GitHub
├── LICENSE                      ← MIT
├── pyproject.toml
├── .gitignore
│
├── .claude/                     ← Config Claude Code
│   ├── agents/                  ← Les 10 rôles (subagents)
│   │   ├── seo-audit-menu-orchestrator.md
│   │   ├── seo-audit-menu-fetcher.md
│   │   ├── seo-audit-menu-semantic.md
│   │   ├── seo-audit-menu-link-equity.md
│   │   ├── seo-audit-menu-crawlability.md
│   │   ├── seo-audit-menu-accessibility.md
│   │   ├── seo-audit-menu-performance.md
│   │   ├── seo-audit-menu-architecture.md
│   │   ├── seo-audit-menu-reporter.md
│   │   └── seo-audit-menu-reviewer.md
│   │
│   ├── skills/                  ← Les expertises (chargées dans les agents)
│   │   ├── seo-audit-menu-fetcher/        (avec scripts)
│   │   ├── seo-audit-menu-parser/         (avec scripts)
│   │   ├── seo-audit-menu-semantic/
│   │   ├── seo-audit-menu-link-equity/    (avec references)
│   │   ├── seo-audit-menu-crawlability/   (avec scripts)
│   │   ├── seo-audit-menu-accessibility/  (avec references)
│   │   ├── seo-audit-menu-performance/    (avec references)
│   │   ├── seo-audit-menu-architecture/
│   │   ├── seo-audit-menu-comparator/     (avec scripts)
│   │   └── seo-audit-menu-reporter/       (avec scripts)
│   │
│   └── commands/
│       └── audit-menu.md        ← Slash command /audit-menu
│
├── audits/                      ← Outputs — un sous-dossier par audit
│   └── .gitkeep                 (gitignored sauf ce fichier)
│
├── shared/                      ← Code Python partagé entre scripts
│   ├── __init__.py
│   ├── severity.py              ← Issue, Severity, Verdict
│   └── html_utils.py
│
├── knowledge/                   ← Base de connaissances SEO globale
│   └── README.md
│
└── tests/
    ├── fixtures/
    └── test_parser.py
```

## Flux d'exécution d'un audit

Quand l'utilisateur tape `/audit-menu` (ou demande un audit en langage naturel), le flux est :

1. **Intake** — L'orchestrateur ouvre le dialogue maïeutique : mode ? URL ? contraintes ?
2. **Collecte** — L'orchestrateur invoque le fetcher-agent, qui récupère les pages et stocke dans `audits/{date}-{site}/pages/`
3. **Analyse parallèle** — L'orchestrateur invoque EN PARALLÈLE les 6 spécialistes (semantic, link-equity, crawlability, accessibility, performance, architecture). Chacun lit les pages et produit un JSON de findings dans `audits/{date}-{site}/findings/`
4. **Consolidation** — L'orchestrateur agrège les 6 findings, identifie convergences et tensions
5. **Rédaction** — L'orchestrateur invoque le reporter-agent avec la consolidation. Le reporter produit le rapport MD + HTML
6. **Review** — L'orchestrateur invoque le reviewer-agent. Si faille détectée → retour à l'étape concernée. Sinon validation.
7. **Livraison** — Rapport final déposé dans `audits/{date}-{site}/reports/`

## Règles interdites pour Claude Code

- Ne JAMAIS lancer un audit sans phase maïeutique préalable
- Ne JAMAIS écrire un rapport sans section "JE NE PEUX PAS VÉRIFIER"
- Ne JAMAIS inventer une règle SEO sans la tracer à une source dans `.claude/skills/*/references/`
- Ne pas ajouter de dépendances Python lourdes sans validation
- Ne pas créer de Docker / Dashboard web / UI sans demande explicite
- Ne pas mettre d'emojis décoratifs dans le code (ok dans les rapports pour les severités)

## Conventions de code

- Python 3.10+, type hints partout
- `@dataclass` pour les structures, pas de dicts nus
- Docstrings en français, variables en anglais
- Messages utilisateur en français
- Aucun fichier Python > 500 lignes
- Les scripts produisent JSON sur stdout, logs sur stderr, exit code explicite

## État actuel du projet

**Fait :**
- [x] Architecture agents + skills + commands
- [x] Slash command `/audit-menu`
- [x] Les 10 agents définis
- [x] Les skills correspondants avec références SEO

**À faire :**
- [ ] Test sur un vrai cas client
- [ ] Génération rapport HTML (MD seulement pour l'instant)
- [ ] Support CSV Screaming Frog
- [ ] Autres types d'audits : `seo-audit-internal-links`, `seo-audit-migration`, `seo-audit-cwv`
