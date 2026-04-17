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

## Script 2 : `scripts/fetch_authenticated.js` — URLs protégées (Node.js + Playwright)

Script Node.js autonome qui utilise Playwright avec un **profil Chromium dédié et persistant**. Pas besoin de Playwright MCP — le script gère tout lui-même.

### Pré-requis

Installer les dépendances Node.js (une seule fois) :
```bash
cd .claude/skills/seo-audit-menu-fetcher/scripts && npm install
```

### Comment ça marche

1. Le script crée un profil Chromium isolé dans `./audits/.playwright-profiles/{hostname}/`
2. **Première exécution** : la session n'existe pas encore → une fenêtre Chromium s'ouvre, l'utilisateur se connecte manuellement (~30s), le script détecte automatiquement la fin du login par polling
3. **Exécutions suivantes** : le profil est réutilisé automatiquement tant que la session n'a pas expiré — aucune intervention manuelle nécessaire
4. Si la session a expiré, le script re-détecte la page de login et redemande un login manuel

### Utilisation

```bash
node .claude/skills/seo-audit-menu-fetcher/scripts/fetch_authenticated.js \
  --url https://staging.example.com/admin \
  --output-dir audits/{AUDIT_ID}/pages/ \
  --label homepage-auth
```

Options :
- `--url` (requis) : URL à récupérer
- `--output-dir` (requis) : dossier de destination
- `--label` (défaut: `page`) : préfixe des fichiers de sortie
- `--profile-dir` (optionnel) : chemin du profil Playwright (défaut: `./audits/.playwright-profiles/{hostname}/`)
- `--viewport desktop|mobile` (optionnel) : viewport à utiliser. `desktop` = 1920x1080, `mobile` = 390x844 (iPhone 14) avec User-Agent mobile et touch activé. Si omis, Playwright utilise son viewport par défaut (rétrocompatibilité).

### Ce qu'il produit

- `{label}[-{viewport}]-rendered.html` : DOM rendu complet après exécution JS et hydratation (3s d'attente)
- `{label}[-{viewport}]-screenshot.png` : capture d'écran pour référence visuelle
- JSON de résultat sur stdout (structure compatible avec `fetch_public.py`, champ `viewport` ajouté)

Le suffixe `[-{viewport}]` n'apparaît que si `--viewport` est spécifié. Sans `--viewport`, les fichiers gardent l'ancien nommage (`{label}-rendered.html`) pour ne pas casser les audits antérieurs.

**Note :** en mode authentifié, seul le DOM rendu est capturé (pas le HTML source pré-JS). C'est documenté dans le JSON de sortie (`file_source: null`).

### Codes de sortie

- `0` : succès
- `1` : login échoué après tentative manuelle
- `2` : erreur réseau / navigation
- `3` : erreur inattendue

### Capture du burger menu

Le script détecte automatiquement les boutons burger (via `aria-controls` + `aria-expanded`, exclusion des boutons dans `form`/`[role="search"]`) et capture les liens du panneau ouvert.

**Méthode de détection : diff DOM.** Le script collecte tous les `<a href>` AVANT le clic, clique le burger, puis collecte APRÈS. Les liens nouveaux = contenu du burger. Si aucun lien nouveau n'apparaît (cas CSS hidden : le menu est dans le DOM mais masqué), le script tombe en fallback sur `#${ariaControls}` pour lire le panneau directement.

**Limitation connue du diff DOM.** Si le burger injecte un lien qui existe déjà ailleurs dans la page (ex : `/etablissements` dans le footer ET dans le burger), le diff par href ne le comptera pas comme lien du burger (il existait déjà avant le clic). Dans ce cas, le fallback `#ariaControls` est plus fiable — il lit tous les liens du panneau indépendamment du diff. Quand `detection_method: "aria_controls_panel"` est indiqué dans le JSON, les liens sont exhaustifs. Quand `detection_method: "dom_diff"`, des liens dupliqués sitewide peuvent manquer.

**Recommandation aux agents d'analyse :** croiser le fichier `*-burger.json` avec les liens du footer pour vérifier si des URLs importantes sont dans les deux zones.

### Ce qui NE marche PAS (et pourquoi)

Ces trois approches ont été testées et échouent systématiquement sur Windows :

1. **Partager le profil Chrome système** : Windows pose un lock fichier sur le `user-data-dir` quand Chrome tourne. Impossible de le réutiliser dans un second processus. Erreur garantie.

2. **Copier le profil Chrome** : Les cookies sont chiffrés avec Windows DPAPI, lié au compte Windows ET au fichier `Local State` original. Une copie du profil donne des cookies illisibles — Playwright ne peut pas les déchiffrer.

3. **Utiliser `channel: 'chrome'` dans Playwright** : Ça pointe vers le Chrome système installé sur la machine, ce qui retombe sur les problèmes 1 et 2. On utilise le Chromium bundlé par Playwright (pas d'option `channel`), avec un profil dédié qui nous appartient.

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
