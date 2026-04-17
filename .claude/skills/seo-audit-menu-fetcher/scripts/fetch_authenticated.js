#!/usr/bin/env node
/**
 * fetch_authenticated.js — Récupération d'URLs protégées via Playwright (profil persistant).
 *
 * Crée un profil Chromium dédié et isolé. À la première exécution, l'utilisateur
 * se connecte manuellement dans la fenêtre Playwright. Les exécutions suivantes
 * réutilisent le profil (session persistante) tant que les cookies n'expirent pas.
 *
 * POURQUOI pas le Chrome système :
 *   - Windows verrouille le user-data-dir quand Chrome tourne (lock fichier)
 *   - Copier le profil ne marche pas : cookies chiffrés DPAPI, liés au profil original
 *   - On utilise le Chromium bundlé Playwright avec un profil dédié à nous
 *
 * Usage :
 *   node fetch_authenticated.js --url URL --output-dir DIR --label LABEL [--profile-dir DIR] [--viewport desktop|mobile]
 *
 * Codes de sortie :
 *   0 : succès
 *   1 : login échoué après tentative manuelle
 *   2 : erreur réseau / navigation
 *   3 : erreur inattendue
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
// --- Patterns de détection de framework JS ---
const SPA_PATTERNS = {
  'Next.js': [/__NEXT_DATA__/i, /id="__next"/i],
  'Nuxt': [/__NUXT__/i, /id="__nuxt"/i, /__NUXT_DATA__/i],
  'React (generic)': [/react-dom/i, /_reactRootContainer/i, /data-reactroot/i],
  'Vue': [/vue\.(min\.)?js/i, /data-v-[a-f0-9]/i],
  'Angular': [/ng-version=/i, /ng-app=/i, /\[ng-/i],
  'Svelte/SvelteKit': [/__SVELTE__/i, /svelte-[a-z0-9]/i],
  'Gatsby': [/___gatsby/i, /id="___gatsby"/i],
  'Remix': [/__remixContext/i, /__remixRouteModules/i],
};

// --- Viewports prédéfinis ---
const VIEWPORTS = {
  desktop: { width: 1920, height: 1080 },
  mobile: { width: 390, height: 844 },  // iPhone 14
};

// User-Agent mobile réaliste (Googlebot indexe en mobile-first depuis 2023)
const MOBILE_USER_AGENT =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 ' +
  '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

// --- Patterns de détection de page de login ---
// Ancrés avec (?:\/|$|\?) pour éviter les faux positifs (ex: /author, /loginstatus)
const LOGIN_PATTERNS = [
  /accounts\.google\.com/i,
  /login\.microsoftonline\.com/i,
  /\/login(?:\/|$|\?)/i,
  /\/signin(?:\/|$|\?)/i,
  /\/sign-in(?:\/|$|\?)/i,
  /\/auth(?:\/|$|\?)/i,
  /\/connexion(?:\/|$|\?)/i,
  /\/authenticate(?:\/|$|\?)/i,
  /\/sso\//i,
  /\/oauth(?:\/|$|\?)/i,
  /\/cas\/login/i,
];

/**
 * Détecte le framework JS à partir du HTML rendu.
 */
function detectFramework(html) {
  for (const [name, patterns] of Object.entries(SPA_PATTERNS)) {
    for (const pat of patterns) {
      if (pat.test(html)) {
        return name;
      }
    }
  }
  return null;
}

/**
 * Vérifie si l'URL courante ressemble à une page de login.
 */
function isLoginPage(currentUrl) {
  for (const pat of LOGIN_PATTERNS) {
    if (pat.test(currentUrl)) {
      return true;
    }
  }
  return false;
}

/**
 * Attend que l'utilisateur termine son login.
 * Polling de l'URL courante toutes les 2s, jusqu'à ce qu'elle ne soit plus une page de login.
 * Retourne true si login détecté, false si timeout.
 */
async function waitForLoginCompletion(page, maxMs) {
  const intervalMs = 2000;
  let elapsed = 0;
  while (elapsed < maxMs) {
    await new Promise(r => setTimeout(r, intervalMs));
    elapsed += intervalMs;
    try {
      const current = page.url();
      if (!isLoginPage(current)) {
        return true;
      }
    } catch (_) {
      // page peut être en transition, on continue
    }
  }
  return false;
}

/**
 * Collecte tous les liens <a href> de la page avec leur texte.
 * Retourne un Set de "href|||text" pour diff rapide.
 */
async function collectAllLinks(page) {
  return page.evaluate(() => {
    return Array.from(document.querySelectorAll('a[href]')).map(a => ({
      href: a.href,
      text: (a.textContent || '').trim().slice(0, 200),
    }));
  });
}

/**
 * Détecte et ouvre les boutons burger/menu mobile de la page.
 * Utilise une approche diff DOM : capture les liens avant et après le clic
 * pour identifier les liens injectés (compatible portails React/Radix).
 * Retourne un tableau des panneaux avec leurs liens.
 */
async function captureBurgerPanels(page) {
  // Sélecteurs ordonnés du plus spécifique au plus large.
  // Les sélecteurs larges (aria-controls*="menu") excluent les boutons
  // dans des formulaires/barres de recherche.
  const BURGER_SELECTORS = [
    'button[aria-controls*="burger" i][aria-expanded]',
    'button[aria-controls*="drawer" i][aria-expanded]',
    'button[aria-controls*="nav" i][aria-expanded]',
    'button[aria-label*="ouvrir le menu" i][aria-expanded]',
    'button[aria-label*="open menu" i][aria-expanded]',
    // Sélecteur plus large : aria-controls contient "menu" MAIS pas dans un form/search
    'button[aria-controls*="menu" i][aria-expanded]',
  ];

  const results = [];
  const seen = new Set();

  for (const selector of BURGER_SELECTORS) {
    let buttons;
    try {
      buttons = await page.$$(selector);
    } catch (_) {
      continue;
    }

    for (const button of buttons) {
      const isVisible = await button.isVisible().catch(() => false);
      if (!isVisible) continue;

      const ariaControls = await button.getAttribute('aria-controls');
      const ariaLabel = await button.getAttribute('aria-label');

      // Éviter de cliquer deux fois le même bouton
      const buttonId = ariaControls || ariaLabel || selector;
      if (seen.has(buttonId)) continue;
      seen.add(buttonId);

      const wasExpanded = await button.getAttribute('aria-expanded');
      if (wasExpanded === 'true') continue;

      // Exclure les boutons dans un formulaire/barre de recherche
      const inSearchOrForm = await button.evaluate(el =>
        !!el.closest('form') || !!el.closest('[role="search"]')
      );
      if (inSearchOrForm) continue;

      try {
        // --- Approche diff DOM : capturer les liens AVANT le clic ---
        const linksBefore = await collectAllLinks(page);
        const hrefSetBefore = new Set(linksBefore.map(l => l.href));

        await button.click({ timeout: 3000 });
        await new Promise(r => setTimeout(r, 700));

        // --- Capturer les liens APRÈS le clic ---
        const linksAfter = await collectAllLinks(page);

        // Diff : liens qui sont apparus après le clic = contenu du panneau burger
        const injectedLinks = linksAfter.filter(l => !hrefSetBefore.has(l.href));

        // Si aucun nouveau lien, les liens étaient déjà dans le DOM (CSS hidden)
        // Dans ce cas, capturer tous les liens du panneau aria-controls s'il existe
        let panelLinks = injectedLinks;
        let method = 'dom_diff';

        if (injectedLinks.length === 0 && ariaControls) {
          // Les liens sont dans le DOM mais cachés en CSS — essayer de lire le panneau
          // Utiliser document.getElementById (pas de CSS selector) pour gérer les ids Radix avec ":"
          const panel = await page.evaluateHandle(
            (id) => document.getElementById(id), ariaControls
          ).then(h => h.asElement()).catch(() => null);
          if (panel) {
            panelLinks = await panel.evaluate(el => {
              return Array.from(el.querySelectorAll('a[href]')).map(a => ({
                href: a.href,
                text: (a.textContent || '').trim().slice(0, 200),
              }));
            });
            method = 'aria_controls_panel';
          }
        }

        // --- Panel dump : capture TOUS les liens visibles dans le panneau (pas juste le diff) ---
        let panelDump = { panel_found: false, panel_links: [], panel_links_visible: 0 };
        if (ariaControls) {
          panelDump = await page.evaluate((pId) => {
            const panel = document.getElementById(pId);
            if (!panel) return { panel_found: false, panel_links: [], panel_links_visible: 0 };
            const links = [];
            for (const el of panel.querySelectorAll('a[href], button')) {
              const rect = el.getBoundingClientRect();
              const style = window.getComputedStyle(el);
              const visible = style.display !== 'none' && style.visibility !== 'hidden'
                && style.opacity !== '0' && rect.width > 0 && rect.height > 0;
              links.push({
                tag: el.tagName.toLowerCase(),
                href: el.getAttribute('href'),
                text: (el.textContent || '').trim().slice(0, 100),
                visible,
              });
            }
            return {
              panel_found: true,
              panel_links: links,
              panel_links_visible: links.filter(l => l.visible).length,
            };
          }, ariaControls);
        }

        results.push({
          trigger: { ariaLabel, ariaControls, selector },
          panel_found: panelLinks.length > 0 || panelDump.panel_found,
          links_count: panelLinks.length,
          links: panelLinks,
          detection_method: method,
          panel_dump: panelDump,
          captured_at: new Date().toISOString(),
        });

        // Refermer avec Escape
        await page.keyboard.press('Escape').catch(() => {});
        await new Promise(r => setTimeout(r, 300));
      } catch (err) {
        results.push({
          trigger: { ariaLabel, ariaControls, selector },
          panel_found: false,
          links_count: 0,
          links: [],
          error: err.message,
          captured_at: new Date().toISOString(),
        });
      }
    }
  }

  return results;
}

/**
 * Parse les arguments CLI.
 */
function parseArgs() {
  const args = { url: null, outputDir: null, label: 'page', profileDir: null, viewport: null };
  const argv = process.argv.slice(2);

  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case '--url':
        args.url = argv[++i];
        break;
      case '--output-dir':
        args.outputDir = argv[++i];
        break;
      case '--label':
        args.label = argv[++i];
        break;
      case '--profile-dir':
        args.profileDir = argv[++i];
        break;
      case '--viewport':
        args.viewport = argv[++i];
        break;
    }
  }

  if (!args.url) {
    console.error('[fetch_authenticated] ✗ Argument --url requis');
    process.exit(3);
  }
  if (!args.outputDir) {
    console.error('[fetch_authenticated] ✗ Argument --output-dir requis');
    process.exit(3);
  }
  if (args.viewport && !VIEWPORTS[args.viewport]) {
    console.error(`[fetch_authenticated] ✗ Viewport inconnu : ${args.viewport}. Valeurs acceptées : desktop, mobile`);
    process.exit(3);
  }

  // Profil par défaut : ./audits/.playwright-profiles/{hostname}/
  if (!args.profileDir) {
    const hostname = new URL(args.url).hostname;
    args.profileDir = path.join('.', 'audits', '.playwright-profiles', hostname);
  }

  return args;
}

/**
 * Point d'entrée principal.
 */
async function main() {
  const args = parseArgs();
  const { url, outputDir, label, profileDir, viewport: viewportArg } = args;

  // Résolution du viewport et du suffixe fichier
  // Si --viewport fourni → suffixe dans les noms de fichiers (ex: homepage-mobile-rendered.html)
  // Si absent → ancien pattern sans suffixe pour rétrocompatibilité
  const viewportName = viewportArg || null;
  const viewportSize = viewportName ? VIEWPORTS[viewportName] : null;
  const fileSuffix = viewportName ? `-${viewportName}` : '';

  // Créer les dossiers nécessaires
  fs.mkdirSync(profileDir, { recursive: true });
  fs.mkdirSync(outputDir, { recursive: true });

  let context;

  try {
    console.error(`[fetch_authenticated] Lancement Chromium avec profil : ${profileDir}`);
    if (viewportName) {
      console.error(`[fetch_authenticated] Viewport : ${viewportName} (${viewportSize.width}x${viewportSize.height})`);
    }

    // Lancer Playwright avec le Chromium bundlé (PAS le Chrome système).
    // On n'utilise PAS channel: 'chrome' car ça pointerait vers le Chrome système,
    // dont le profil est verrouillé par Windows quand Chrome tourne.
    // Sans option channel, Playwright utilise son Chromium bundlé avec un profil dédié.
    const contextOptions = { headless: false };
    if (viewportSize) {
      contextOptions.viewport = viewportSize;
    }
    if (viewportName === 'mobile') {
      contextOptions.userAgent = MOBILE_USER_AGENT;
      contextOptions.isMobile = true;
      contextOptions.hasTouch = true;
    }
    context = await chromium.launchPersistentContext(profileDir, contextOptions);

    const page = context.pages()[0] || await context.newPage();

    // --- Première navigation ---
    console.error(`[fetch_authenticated] Navigation vers : ${url}`);
    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
    } catch (navError) {
      // Erreur réseau / timeout de navigation
      const result = {
        success: false,
        url,
        label,
        fetched_at: new Date().toISOString(),
        reason: `Erreur de navigation : ${navError.message}`,
        suggestion: 'Vérifier que le site est accessible et que l\'URL est correcte.',
      };
      console.log(JSON.stringify(result, null, 2));
      await context.close();
      process.exit(2);
    }

    // --- Vérification de session ---
    const currentUrl = page.url();

    if (isLoginPage(currentUrl)) {
      console.error(
        '[fetch_authenticated] ⚠ Session non authentifiée pour ce profil.\n' +
        '  Une fenêtre Chromium s\'est ouverte. Connecte-toi manuellement dans cette fenêtre.\n' +
        '  Le script détectera automatiquement la fin du login (polling toutes les 2s, timeout 180s).'
      );

      const loginCompleted = await waitForLoginCompletion(page, 180000);

      if (!loginCompleted) {
        console.error('[fetch_authenticated] ✗ Timeout dépassé (180s). Login non détecté. Abandon.');
        const result = {
          success: false,
          url,
          label,
          fetched_at: new Date().toISOString(),
          reason: 'Timeout dépassé en attente du login manuel (180s)',
          suggestion: 'Relancer le script et se connecter dans les 3 minutes.',
        };
        console.log(JSON.stringify(result, null, 2));
        await context.close();
        process.exit(1);
      }

      // Re-navigation après login détecté pour garantir networkidle sur l'URL cible
      console.error(`[fetch_authenticated] Login détecté. Re-navigation vers : ${url}`);
      try {
        await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
      } catch (navError) {
        const result = {
          success: false,
          url,
          label,
          fetched_at: new Date().toISOString(),
          reason: `Erreur de re-navigation après login : ${navError.message}`,
          suggestion: 'Vérifier la connexion et réessayer.',
        };
        console.log(JSON.stringify(result, null, 2));
        await context.close();
        process.exit(2);
      }

      // Vérification post-login
      const postLoginUrl = page.url();
      if (isLoginPage(postLoginUrl)) {
        console.error('[fetch_authenticated] ✗ Session encore non authentifiée après tentative manuelle. Abandon.');
        const result = {
          success: false,
          url,
          label,
          fetched_at: new Date().toISOString(),
          reason: 'Session non authentifiée après tentative de login manuel',
          suggestion: 'Vérifier les identifiants. Le profil Playwright est conservé, relancer pour réessayer.',
        };
        console.log(JSON.stringify(result, null, 2));
        await context.close();
        process.exit(1);
      }
    }

    // --- Succès : capture du contenu ---

    // Attente supplémentaire pour l'hydratation JS (Next.js, etc.)
    console.error('[fetch_authenticated] Attente 3s pour hydratation JS...');
    await new Promise(r => setTimeout(r, 3000));

    // --- Capture des panneaux burger ---
    // captureBurgerPanels fait maintenant les DEUX méthodes en une seule ouverture :
    // 1. Diff DOM (liens injectés dynamiquement)
    // 2. Panel dump (tous les liens visibles dans le panneau ouvert)
    const burgerCapture = await captureBurgerPanels(page);

    let burgerFile = null;
    if (burgerCapture.length > 0) {
      burgerFile = path.join(outputDir, `${label}${fileSuffix}-burger.json`);
      fs.writeFileSync(burgerFile, JSON.stringify(burgerCapture, null, 2), 'utf-8');
      const diffLinks = burgerCapture.reduce((sum, b) => sum + (b.links_count || 0), 0);
      const dumpVisible = burgerCapture.reduce((sum, b) => sum + (b.panel_dump?.panel_links_visible || 0), 0);
      console.error(`[fetch_authenticated] ✓ Burger capturé : ${diffLinks} liens (diff DOM), ${dumpVisible} liens visibles (panel dump) : ${burgerFile}`);
    } else {
      console.error('[fetch_authenticated]   Aucun bouton burger détecté sur cette page.');
    }

    // Capture du HTML rendu
    const html = await page.content();
    const renderedPath = path.join(outputDir, `${label}${fileSuffix}-rendered.html`);
    fs.writeFileSync(renderedPath, html, 'utf-8');
    console.error(`[fetch_authenticated] ✓ HTML rendu sauvegardé : ${renderedPath}`);

    // Screenshot
    const screenshotPath = path.join(outputDir, `${label}${fileSuffix}-screenshot.png`);
    await page.screenshot({ path: screenshotPath, fullPage: false });
    console.error(`[fetch_authenticated] ✓ Screenshot sauvegardé : ${screenshotPath}`);

    // Détection framework
    const framework = detectFramework(html);
    if (framework) {
      console.error(`[fetch_authenticated]   Framework détecté : ${framework}`);
    }

    // --- JSON de résultat (sur stdout, structure compatible avec fetch_public.py) ---
    const result = {
      success: true,
      url,
      label,
      mode: 'authenticated',
      viewport: viewportName,
      file_source: null,
      file_rendered: renderedPath,
      file_screenshot: screenshotPath,
      file_burger: burgerFile,
      burger_diff_links: burgerCapture.reduce((sum, b) => sum + (b.links_count || 0), 0),
      burger_panel_links_visible: burgerCapture.reduce((sum, b) => sum + (b.panel_dump?.panel_links_visible || 0), 0),
      size_bytes: Buffer.byteLength(html, 'utf-8'),
      is_spa: framework !== null,
      framework_detected: framework,
      fetched_at: new Date().toISOString(),
      warnings: [],
      note: 'Audit en mode authentifié. Le HTML source (pré-JS) n\'est pas disponible — ' +
            'seul le DOM rendu est capturé. Privilégier le DOM rendu pour l\'analyse.',
    };

    console.log(JSON.stringify(result, null, 2));
    await context.close();
    process.exit(0);

  } catch (error) {
    // Erreur inattendue globale
    console.error(`[fetch_authenticated] ✗ Erreur inattendue : ${error.message}`);
    const result = {
      success: false,
      url: args.url,
      label: args.label,
      fetched_at: new Date().toISOString(),
      reason: `Erreur inattendue : ${error.message}`,
      suggestion: 'Vérifier l\'installation de Playwright (npm install) et réessayer.',
    };
    console.log(JSON.stringify(result, null, 2));
    if (context) {
      try { await context.close(); } catch (_) { /* ignore */ }
    }
    process.exit(3);
  }
}

main();
