---
name: seo-audit-menu-fetcher
description: Récupération de pages web pour audit SEO. Gère les URLs publiques (curl), les sites authentifiés via Playwright MCP (login manuel dans navigateur visible), et les fichiers HTML locaux. Capture HTML source ET DOM rendu pour les SPAs. Utilisé par l'agent seo-audit-menu-fetcher.
---

# Skill : Fetcher de pages

Ce skill permet de récupérer des pages web dans différents modes d'accès. L'agent qui l'utilise doit **toujours** choisir le bon mode en fonction de l'input fourni.

## Arbre de décision — quel script lancer

```
Est-ce une URL ?
├── Non → c'est un fichier local
│         → Utiliser scripts/import_local.py
│
└── Oui → Est-ce une page authentifiée ?
         ├── Non → scripts/fetch_public.py (curl-like)
         │         Peut-on détecter si c'est une SPA ?
         │         ├── Oui → lancer aussi scripts/capture_rendered.py
         │         └── Non → source seulement suffit
         │
         └── Oui → scripts/fetch_authenticated.py (Playwright MCP)
                   Login manuel par l'utilisateur dans fenêtre visible.
```

## Script 1 : `scripts/fetch_public.py` — URLs publiques

Téléchargement simple via `urllib` (pas de dépendance externe).

### Utilisation

```bash
python3 .claude/skills/seo-audit-menu-fetcher/scripts/fetch_public.py \
  --url https://example.com \
  --output-dir audits/{AUDIT_ID}/pages/ \
  --label homepage
```

### Ce qu'il fait

1. Télécharge le HTML source via GET HTTP
2. Sauvegarde dans `{output_dir}/{label}-source.html`
3. Détecte si c'est une SPA (présence de patterns React, Vue, Angular, Next, Nuxt...)
4. Retourne un JSON avec métadonnées sur stdout

### Format de sortie JSON

```json
{
  "success": true,
  "url": "https://example.com",
  "label": "homepage",
  "file_source": "audits/.../homepage-source.html",
  "file_rendered": null,
  "size_bytes": 12345,
  "http_status": 200,
  "is_spa": true,
  "framework_detected": "Next.js",
  "fetched_at": "2026-04-16T...",
  "warnings": []
}
```

### Cas d'échec

Si HTTP 403, 404, 500, timeout : JSON avec `"success": false` et `"reason"` explicite.

Exemples de `reason` :
- `"HTTP 403 Forbidden — le site bloque les requêtes automatisées"`
- `"HTTP 404 Not Found — l'URL n'existe pas"`
- `"Connection timeout (10s) — site indisponible ou bloqué"`
- `"SSL certificate error — vérifier la configuration HTTPS"`

## Script 2 : `scripts/fetch_authenticated.py` — URLs protégées

Utilise Playwright MCP. L'utilisateur se connecte manuellement dans la fenêtre visible.

### Pré-requis

Playwright MCP doit être configuré dans `~/.claude.json` ou dans le projet :
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"]
    }
  }
}
```

### Workflow

1. L'agent appelle le script avec l'URL à auditer
2. Le script affiche une fenêtre Chrome visible
3. Navigue vers l'URL de login (si fourni) OU directement vers l'URL cible
4. **L'UTILISATEUR se connecte manuellement** dans la fenêtre
5. Une fois connecté, l'utilisateur signale à Claude "je suis connecté"
6. Claude reprend la main, navigue vers l'URL cible, capture le HTML

### Utilisation

```bash
# L'agent Playwright MCP se charge des appels browser_*.
# Le script sert à orchestrer la séquence et sauvegarder les outputs.
python3 .claude/skills/seo-audit-menu-fetcher/scripts/fetch_authenticated.py \
  --url https://staging.example.com/admin \
  --output-dir audits/{AUDIT_ID}/pages/ \
  --label homepage-auth
```

### Ce qu'il produit

- `{label}-source.html` : HTML source initial (après login, avant rendu JS complet)
- `{label}-rendered.html` : DOM rendu complet après exécution JS
- `{label}-screenshot.png` : capture d'écran pour référence visuelle

## Script 3 : `scripts/import_local.py` — fichiers locaux ou HTML collé

Copie un fichier HTML local dans le dossier d'audit, ou reçoit du HTML sur stdin.

### Utilisation

```bash
# Fichier existant
python3 import_local.py --input /path/to/page.html --output-dir audits/.../pages/ --label homepage

# HTML collé sur stdin
cat page.html | python3 import_local.py --stdin --output-dir audits/.../pages/ --label homepage
```

## Détection de framework JS

Les trois scripts utilisent la même logique de détection SPA. Patterns recherchés :

| Framework | Patterns |
|-----------|----------|
| React | `__NEXT_DATA__`, `react-dom`, `_reactRootContainer`, `data-reactroot` |
| Vue/Nuxt | `__NUXT__`, `vue.min.js`, `data-v-`, `__NUXT_DATA__` |
| Angular | `ng-version=`, `angular.js`, `ng-app`, `[ng-` |
| Svelte/SvelteKit | `__SVELTE__`, `svelte-` |
| Gatsby | `___gatsby`, `gatsby-` |
| Remix | `__remixContext`, `__remixRouteModules` |

Si un de ces patterns est détecté, le JSON de sortie inclut `"is_spa": true` et `"framework_detected": "..."`.

## Règle d'honnêteté radicale

Si un script échoue, il DOIT :
1. Retourner un JSON avec `"success": false`
2. Donner un `"reason"` clair et actionnable
3. Proposer une alternative dans `"suggestion"`
4. Retourner un exit code non-zero (1 pour échec attendu, 2 pour échec réseau, 3 pour erreur inattendue)

Jamais de crash silencieux. Jamais de fake data.
