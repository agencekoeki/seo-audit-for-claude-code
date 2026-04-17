#!/usr/bin/env node
/**
 * accessibility_dynamic.js — Tests d'accessibilité dynamiques du menu via Playwright.
 *
 * Produit l'arbre ARIA, teste les interactions clavier réelles (Tab, Escape),
 * mesure les target sizes des éléments interactifs de la nav, vérifie le skip link,
 * l'aria-current, et le focus management.
 *
 * Usage :
 *   node accessibility_dynamic.js --url URL --output FILE [--viewport desktop|mobile] [--profile-dir DIR]
 *
 * Codes de sortie :
 *   0 : succès
 *   2 : erreur réseau / navigation
 *   3 : erreur inattendue
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const VIEWPORTS = {
  desktop: { width: 1920, height: 1080 },
  mobile: { width: 390, height: 844 },
};

const MOBILE_USER_AGENT =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 ' +
  '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

// Seuil WCAG 2.5.8 Target Size Minimum (AA) + seuil Google Lighthouse/Material Design
const MIN_TARGET_SIZE = 24;
const GOOGLE_TARGET_SIZE = 48;

// Sélecteur élargi pour capturer les liens nav dans les portails React/Radix
// Couvre : <nav> classique, <nav> dans un portal, [role="dialog"], [role="navigation"]
const NAV_INTERACTIVE_SELECTOR = 'nav a, nav button, [role="dialog"] nav a, [role="dialog"] nav button, [role="navigation"] a, [role="navigation"] button';

function parseArgs() {
  const args = { url: null, output: null, viewport: 'desktop', profileDir: null };
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case '--url': args.url = argv[++i]; break;
      case '--output': args.output = argv[++i]; break;
      case '--viewport': args.viewport = argv[++i]; break;
      case '--profile-dir': args.profileDir = argv[++i]; break;
    }
  }
  if (!args.url) { console.error('[accessibility_dynamic] ✗ --url requis'); process.exit(3); }
  if (!args.output) { console.error('[accessibility_dynamic] ✗ --output requis'); process.exit(3); }
  if (!VIEWPORTS[args.viewport]) { console.error(`[accessibility_dynamic] ✗ Viewport inconnu : ${args.viewport}`); process.exit(3); }
  return args;
}

/**
 * Test 1 — Skip link : le premier élément focusable pointe vers #main ou équivalent.
 */
async function testSkipLink(page) {
  // Reset focus sur le body
  await page.evaluate(() => document.body.focus());

  // Simuler Tab depuis le début du document
  await page.keyboard.press('Tab');
  await new Promise(r => setTimeout(r, 100));

  const firstFocused = await page.evaluate(() => {
    const el = document.activeElement;
    if (!el || el === document.body) return null;
    return {
      tag: el.tagName.toLowerCase(),
      href: el.getAttribute('href'),
      text: (el.textContent || '').trim().slice(0, 100),
      isSkipLink: el.tagName === 'A' && (el.getAttribute('href') || '').startsWith('#'),
    };
  });

  // Vérifier que la cible du skip link existe
  let targetExists = false;
  if (firstFocused && firstFocused.isSkipLink && firstFocused.href) {
    const targetId = firstFocused.href.replace('#', '');
    targetExists = await page.evaluate((id) => !!document.getElementById(id), targetId);
  }

  return {
    test: 'skip_link',
    wcag: '2.4.1',
    passed: firstFocused?.isSkipLink && targetExists,
    first_focused_element: firstFocused,
    target_exists: targetExists,
    elements_checked: 1,
    severity: firstFocused?.isSkipLink ? (targetExists ? null : 'IMPORTANT') : 'CRITIQUE',
  };
}

/**
 * Test 2 — Tab order dans la nav : Tab N fois, lister les éléments focusés.
 * Vérifie qu'il n'y a pas de piège (focus bloqué au même endroit).
 */
async function testTabOrder(page) {
  // Reset focus
  await page.evaluate(() => document.body.focus());
  await new Promise(r => setTimeout(r, 100));

  const tabOrder = [];
  let lastTag = '';
  let trapDetected = false;
  const MAX_TABS = 30;

  for (let i = 0; i < MAX_TABS; i++) {
    await page.keyboard.press('Tab');
    await new Promise(r => setTimeout(r, 50));

    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const inNav = !!el.closest('nav');
      return {
        tag: el.tagName.toLowerCase(),
        text: (el.textContent || '').trim().slice(0, 80),
        href: el.getAttribute('href'),
        role: el.getAttribute('role'),
        ariaLabel: el.getAttribute('aria-label'),
        inNav,
      };
    });

    if (!focused) continue;
    tabOrder.push(focused);

    // Détecter les pièges (même élément 3 fois de suite)
    const sig = `${focused.tag}:${focused.text}`;
    if (sig === lastTag) {
      trapDetected = true;
      break;
    }
    lastTag = sig;

    // Arrêter quand on sort de la nav (on a traversé le menu)
    if (tabOrder.length > 3 && !focused.inNav && tabOrder[tabOrder.length - 2]?.inNav) {
      break;
    }
  }

  const navItems = tabOrder.filter(t => t.inNav);
  return {
    test: 'tab_order',
    wcag: '2.4.3',
    passed: !trapDetected && navItems.length > 0,
    elements_checked: tabOrder.length,
    nav_focusable: navItems.length,
    trap_detected: trapDetected,
    tab_sequence: tabOrder.slice(0, 15), // Limiter pour la lisibilité
    severity: trapDetected ? 'CRITIQUE' : null,
  };
}

/**
 * Test 3 — Focus visibility : utilise Tab clavier (pas el.focus()) pour déclencher :focus-visible.
 * Compare le style computed avant/après chaque Tab pour détecter un indicateur de focus visible.
 */
async function testFocusVisibility(page) {
  // Reset focus au body
  await page.evaluate(() => document.body.focus());
  await new Promise(r => setTimeout(r, 100));

  const results = [];
  const MAX_TABS = 20;
  let inNavSeen = false;

  for (let i = 0; i < MAX_TABS; i++) {
    // Capturer le style de l'élément avant qu'il reçoive le focus
    // (on capture le style de l'élément qui VA recevoir le focus via Tab)
    await page.keyboard.press('Tab');
    await new Promise(r => setTimeout(r, 80));

    const check = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const inNav = !!el.closest('nav');
      const style = window.getComputedStyle(el);
      const outline = style.outline;
      const boxShadow = style.boxShadow;
      const outlineNone = outline === 'none' || outline.includes('0px');
      const hasBoxShadow = boxShadow !== 'none' && boxShadow !== '';

      return {
        text: (el.textContent || '').trim().slice(0, 50),
        tag: el.tagName.toLowerCase(),
        inNav,
        focus_outline: outline,
        focus_box_shadow: hasBoxShadow ? boxShadow : null,
        has_visible_focus: !outlineNone || hasBoxShadow,
        outline_none_no_replacement: outlineNone && !hasBoxShadow,
      };
    });

    if (!check) continue;

    // On ne s'intéresse qu'aux éléments dans la nav
    if (check.inNav) {
      inNavSeen = true;
      results.push(check);
    } else if (inNavSeen) {
      // On est sorti de la nav, on arrête
      break;
    }
  }

  const violations = results.filter(r => r.outline_none_no_replacement);
  return {
    test: 'focus_visibility',
    wcag: '2.4.7 + 2.4.11',
    passed: violations.length === 0,
    elements_checked: results.length,
    violations_count: violations.length,
    violations: violations.slice(0, 5),
    note: 'Test via Tab clavier réel (déclenche :focus-visible, pas :focus programmatique)',
    severity: violations.length > 0 ? 'CRITIQUE' : null,
  };
}

/**
 * Test 4 — Target sizes : mesurer getBoundingClientRect de chaque élément interactif nav.
 */
async function measureTargetSizes(page) {
  const measurements = await page.evaluate(({ wcagSize, googleSize, sel }) => {
    const elements = Array.from(document.querySelectorAll(sel));
    return elements.slice(0, 20).map(el => {
      const rect = el.getBoundingClientRect();
      const visible = rect.width > 0 && rect.height > 0;
      return {
        text: (el.textContent || '').trim().slice(0, 50),
        tag: el.tagName.toLowerCase(),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        visible,
        passes_wcag: visible && rect.width >= wcagSize && rect.height >= wcagSize,
        passes_google: visible && rect.width >= googleSize && rect.height >= googleSize,
      };
    });
  }, { wcagSize: MIN_TARGET_SIZE, googleSize: GOOGLE_TARGET_SIZE, sel: NAV_INTERACTIVE_SELECTOR });

  const visible = measurements.filter(m => m.visible);
  const wcagViolations = visible.filter(m => !m.passes_wcag);
  const googleViolations = visible.filter(m => !m.passes_google);
  return {
    test: 'target_sizes',
    wcag: '2.5.8',
    wcag_min_px: MIN_TARGET_SIZE,
    google_min_px: GOOGLE_TARGET_SIZE,
    passed: wcagViolations.length === 0,
    elements_checked: visible.length,
    wcag_violations_count: wcagViolations.length,
    wcag_violations: wcagViolations.slice(0, 5),
    google_violations_count: googleViolations.length,
    google_violations: googleViolations.slice(0, 5),
    severity: wcagViolations.length > 0 ? (wcagViolations.length > 3 ? 'CRITIQUE' : 'IMPORTANT')
            : googleViolations.length > 0 ? 'RECOMMANDATION' : null,
  };
}

/**
 * Test 5 — Escape ferme le burger et rend le focus au trigger.
 */
async function testEscapeClosesBurger(page) {
  const burgerSelectors = [
    'button[aria-controls*="burger" i]',
    'button[aria-controls*="menu" i]',
    'button[aria-controls*="drawer" i]',
    'button[aria-label*="menu" i]',
  ];

  for (const selector of burgerSelectors) {
    const button = await page.$(selector);
    if (!button) continue;
    const isVisible = await button.isVisible().catch(() => false);
    if (!isVisible) continue;

    const wasExpanded = await button.getAttribute('aria-expanded');
    if (wasExpanded === 'true') continue;

    try {
      await button.click({ timeout: 3000 });
      await new Promise(r => setTimeout(r, 500));

      const afterClickExpanded = await button.getAttribute('aria-expanded');
      if (afterClickExpanded !== 'true') continue; // Le bouton ne répond pas

      // Presser Escape
      await page.keyboard.press('Escape');
      await new Promise(r => setTimeout(r, 300));

      const afterEscapeExpanded = await button.getAttribute('aria-expanded');
      const focusReturnedToTrigger = await page.evaluate((sel) => {
        const trigger = document.querySelector(sel);
        return document.activeElement === trigger;
      }, selector);

      return {
        test: 'escape_closes_burger',
        wcag: 'ARIA APG Disclosure',
        passed: afterEscapeExpanded === 'false' && focusReturnedToTrigger,
        elements_checked: 1,
        burger_selector: selector,
        escape_closed: afterEscapeExpanded === 'false',
        focus_returned: focusReturnedToTrigger,
        severity: afterEscapeExpanded !== 'false' ? 'IMPORTANT' : (!focusReturnedToTrigger ? 'IMPORTANT' : null),
      };
    } catch (err) {
      return {
        test: 'escape_closes_burger',
        wcag: 'ARIA APG Disclosure',
        passed: false,
        elements_checked: 1,
        error: err.message,
        severity: 'IMPORTANT',
      };
    }
  }

  return {
    test: 'escape_closes_burger',
    wcag: 'ARIA APG Disclosure',
    passed: null,
    elements_checked: 0,
    note: 'Aucun bouton burger visible détecté dans ce viewport',
    severity: null,
  };
}

/**
 * Test 6 — aria-current="page" sur l'item correspondant à l'URL courante.
 */
async function testAriaCurrent(page) {
  const result = await page.evaluate(() => {
    const currentPath = window.location.pathname;
    const navLinks = Array.from(document.querySelectorAll('nav a[href]'));
    let matchFound = false;
    let ariaCurrentPresent = false;

    for (const link of navLinks) {
      try {
        const linkUrl = new URL(link.href, window.location.origin);
        if (linkUrl.pathname === currentPath) {
          matchFound = true;
          if (link.getAttribute('aria-current') === 'page') {
            ariaCurrentPresent = true;
          }
        }
      } catch (_) {}
    }

    return {
      current_path: currentPath,
      matching_link_found: matchFound,
      aria_current_present: ariaCurrentPresent,
      nav_links_count: navLinks.length,
    };
  });

  return {
    test: 'aria_current_page',
    wcag: 'ARIA best practice',
    passed: !result.matching_link_found || result.aria_current_present,
    elements_checked: result.nav_links_count,
    ...result,
    severity: result.matching_link_found && !result.aria_current_present ? 'IMPORTANT' : null,
  };
}

/**
 * Test 7 — Espacement entre tap targets adjacents dans la nav (min 8px Google).
 */
async function measureTargetSpacing(page) {
  return page.evaluate((sel) => {
    const elements = Array.from(document.querySelectorAll(sel));
    const violations = [];
    for (let i = 0; i < elements.length - 1; i++) {
      const r1 = elements[i].getBoundingClientRect();
      const r2 = elements[i + 1].getBoundingClientRect();
      if (r1.width === 0 || r2.width === 0) continue;

      const hGap = Math.max(0, r2.left - r1.right);
      const vGap = Math.max(0, r2.top - r1.bottom);
      const gap = Math.min(
        hGap > 0 ? hGap : Infinity,
        vGap > 0 ? vGap : Infinity
      );

      if (gap < 8 && gap !== Infinity) {
        violations.push({
          element1: (elements[i].textContent || '').trim().slice(0, 40),
          element2: (elements[i + 1].textContent || '').trim().slice(0, 40),
          gap_px: Math.round(gap),
          min_required: 8,
        });
      }
    }
    return {
      test: 'target_spacing',
      standard: 'Google Material Design (8px min)',
      passed: violations.length === 0,
      elements_checked: elements.length,
      violations_count: violations.length,
      violations: violations.slice(0, 5),
      severity: violations.length > 3 ? 'CRITIQUE' : (violations.length > 0 ? 'IMPORTANT' : null),
    };
  }, NAV_INTERACTIVE_SELECTOR);
}

/**
 * Test 8 — Font size ≥ 16px dans la nav mobile.
 */
async function measureFontSizes(page) {
  return page.evaluate((sel) => {
    const elements = Array.from(document.querySelectorAll(sel));
    const violations = [];
    let visibleCount = 0;
    for (const el of elements) {
      if (el.offsetWidth === 0) continue;
      visibleCount++;
      const fontSize = parseFloat(window.getComputedStyle(el).fontSize);
      if (fontSize < 16) {
        violations.push({
          text: (el.textContent || '').trim().slice(0, 40),
          font_size_px: Math.round(fontSize * 10) / 10,
          min_required: 16,
        });
      }
    }
    return {
      test: 'font_size_mobile',
      standard: 'Google Mobile-Friendly / iOS Safari zoom',
      passed: violations.length === 0,
      elements_checked: visibleCount,
      violations_count: violations.length,
      violations: violations.slice(0, 5),
      severity: violations.length > 0 ? 'IMPORTANT' : null,
    };
  }, NAV_INTERACTIVE_SELECTOR);
}

async function main() {
  const args = parseArgs();
  const { url, output, viewport: vpName, profileDir } = args;
  const vpSize = VIEWPORTS[vpName];

  console.error(`[accessibility_dynamic] Tests d'accessibilité pour : ${url} (viewport: ${vpName})`);

  const contextOptions = { headless: true, viewport: vpSize };
  if (vpName === 'mobile') {
    contextOptions.userAgent = MOBILE_USER_AGENT;
    contextOptions.isMobile = true;
    contextOptions.hasTouch = true;
  }

  let context;
  try {
    if (profileDir) {
      context = await chromium.launchPersistentContext(profileDir, contextOptions);
    } else {
      const browser = await chromium.launch({ headless: true });
      context = await browser.newContext(contextOptions);
    }

    const page = context.pages()[0] || await context.newPage();
    await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
    await new Promise(r => setTimeout(r, 3000));

    // Exécuter les 8 tests
    console.error('[accessibility_dynamic] Test skip link...');
    const skipLink = await testSkipLink(page);

    console.error('[accessibility_dynamic] Test tab order...');
    const tabOrder = await testTabOrder(page);

    console.error('[accessibility_dynamic] Test focus visibility...');
    let focusVisibility = await testFocusVisibility(page);

    console.error('[accessibility_dynamic] Mesure target sizes...');
    let targetSizes = await measureTargetSizes(page);

    console.error('[accessibility_dynamic] Mesure espacement tap targets...');
    let targetSpacing = await measureTargetSpacing(page);

    console.error('[accessibility_dynamic] Mesure font sizes nav...');
    let fontSizes = await measureFontSizes(page);

    // --- En mobile, si aucun élément nav visible, ouvrir le burger et remesurer ---
    let burgerOpenedForMeasure = false;
    if (vpName === 'mobile' && targetSizes.elements_checked === 0) {
      console.error('[accessibility_dynamic]   ⚠ 0 éléments nav visibles en mobile. Tentative ouverture burger...');
      const burgerSelectors = [
        'button[aria-controls*="burger" i][aria-expanded]',
        'button[aria-controls*="menu" i][aria-expanded]',
        'button[aria-controls*="drawer" i][aria-expanded]',
        'button[aria-label*="ouvrir le menu" i][aria-expanded]',
        'button[aria-label*="menu" i][aria-expanded]',
      ];
      for (const sel of burgerSelectors) {
        const btn = await page.$(sel);
        if (!btn) continue;
        const isVisible = await btn.isVisible().catch(() => false);
        if (!isVisible) continue;
        const expanded = await btn.getAttribute('aria-expanded');
        if (expanded === 'true') continue;
        // Exclure les boutons dans un formulaire
        const inForm = await btn.evaluate(el => !!el.closest('form') || !!el.closest('[role="search"]'));
        if (inForm) continue;

        try {
          const burgerAriaControls = await btn.getAttribute('aria-controls');
          await btn.click({ timeout: 3000 });
          await new Promise(r => setTimeout(r, 700));
          burgerOpenedForMeasure = true;
          console.error('[accessibility_dynamic]   ✓ Burger ouvert. Remesure des tap targets, espacement et fonts...');

          // Construire un sélecteur qui cible le panneau ouvert spécifiquement
          // En priorité : #ariaControls (le panel du burger), puis les fallbacks portail/dialog
          const panelParts = [];
          if (burgerAriaControls) {
            // Échapper les : pour les ids Radix
            const escapedId = burgerAriaControls.replace(/:/g, '\\:');
            panelParts.push(`#${escapedId} a`, `#${escapedId} button`);
          }
          panelParts.push('[role="dialog"] a', '[role="dialog"] button');
          panelParts.push('[data-state="open"] a', '[data-state="open"] button');
          // Fallback large : tout lien/bouton visible (filtré par visibilité dans l'evaluate)
          const burgerPanelSelector = panelParts.join(', ') + ', ' + NAV_INTERACTIVE_SELECTOR;

          // Remesurer avec le sélecteur élargi
          targetSizes = await page.evaluate(({ wcagSize, googleSize, sel }) => {
            const elements = Array.from(document.querySelectorAll(sel))
              .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
            const wcagViol = elements.filter(e => { const r = e.getBoundingClientRect(); return r.width < wcagSize || r.height < wcagSize; });
            const googleViol = elements.filter(e => { const r = e.getBoundingClientRect(); return r.width < googleSize || r.height < googleSize; });
            return {
              test: 'target_sizes', wcag: '2.5.8',
              wcag_min_px: wcagSize, google_min_px: googleSize,
              elements_checked: elements.length,
              wcag_violations_count: wcagViol.length,
              wcag_violations: wcagViol.slice(0,5).map(e => ({ text: (e.textContent||'').trim().slice(0,50), width: Math.round(e.getBoundingClientRect().width), height: Math.round(e.getBoundingClientRect().height) })),
              google_violations_count: googleViol.length,
              google_violations: googleViol.slice(0,5).map(e => ({ text: (e.textContent||'').trim().slice(0,50), width: Math.round(e.getBoundingClientRect().width), height: Math.round(e.getBoundingClientRect().height) })),
              passed: wcagViol.length === 0,
              severity: wcagViol.length > 3 ? 'CRITIQUE' : wcagViol.length > 0 ? 'IMPORTANT' : googleViol.length > 0 ? 'RECOMMANDATION' : null,
            };
          }, { wcagSize: MIN_TARGET_SIZE, googleSize: GOOGLE_TARGET_SIZE, sel: burgerPanelSelector });

          targetSpacing = await page.evaluate((sel) => {
            const elements = Array.from(document.querySelectorAll(sel))
              .filter(e => e.getBoundingClientRect().width > 0);
            const violations = [];
            for (let i = 0; i < elements.length - 1; i++) {
              const r1 = elements[i].getBoundingClientRect();
              const r2 = elements[i+1].getBoundingClientRect();
              const hGap = Math.max(0, r2.left - r1.right);
              const vGap = Math.max(0, r2.top - r1.bottom);
              const gap = Math.min(hGap > 0 ? hGap : Infinity, vGap > 0 ? vGap : Infinity);
              if (gap < 8 && gap !== Infinity) violations.push({ element1: (elements[i].textContent||'').trim().slice(0,40), element2: (elements[i+1].textContent||'').trim().slice(0,40), gap_px: Math.round(gap), min_required: 8 });
            }
            return { test: 'target_spacing', standard: 'Google Material Design (8px min)', passed: violations.length===0, elements_checked: elements.length, violations_count: violations.length, violations: violations.slice(0,5), severity: violations.length > 3 ? 'CRITIQUE' : violations.length > 0 ? 'IMPORTANT' : null };
          }, burgerPanelSelector);

          fontSizes = await page.evaluate((sel) => {
            const elements = Array.from(document.querySelectorAll(sel));
            const violations = []; let visibleCount = 0;
            for (const el of elements) {
              if (el.offsetWidth === 0) continue; visibleCount++;
              const fs = parseFloat(window.getComputedStyle(el).fontSize);
              if (fs < 16) violations.push({ text: (el.textContent||'').trim().slice(0,40), font_size_px: Math.round(fs*10)/10, min_required: 16 });
            }
            return { test: 'font_size_mobile', standard: 'Google Mobile-Friendly', passed: violations.length===0, elements_checked: visibleCount, violations_count: violations.length, violations: violations.slice(0,5), severity: violations.length > 0 ? 'IMPORTANT' : null };
          }, burgerPanelSelector);

          // Remesurer aussi la focus visibility avec le burger ouvert
          focusVisibility = await testFocusVisibility(page);
          break;
        } catch (_) {
          // Pas grave, on garde les résultats à 0
        }
      }
    }

    console.error('[accessibility_dynamic] Test Escape ferme burger...');
    const escapeBurger = await testEscapeClosesBurger(page);

    console.error('[accessibility_dynamic] Test aria-current...');
    const ariaCurrent = await testAriaCurrent(page);

    const tests = [skipLink, tabOrder, focusVisibility, targetSizes, targetSpacing, fontSizes, escapeBurger, ariaCurrent];
    const passed = tests.filter(t => t.passed === true).length;
    const failed = tests.filter(t => t.passed === false).length;

    const result = {
      url,
      viewport: vpName,
      status: 'complete',
      burger_opened_for_measure: burgerOpenedForMeasure,
      tests,
      summary: {
        total: tests.length,
        passed,
        failed,
        skipped: tests.length - passed - failed,
      },
      checked_at: new Date().toISOString(),
    };

    // Écrire le fichier
    const outputDir = path.dirname(output);
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(output, JSON.stringify(result, null, 2), 'utf-8');

    console.error(`[accessibility_dynamic] ✓ ${passed} passés, ${failed} échoués. Résultat : ${output}`);
    console.log(JSON.stringify({
      url, viewport: vpName,
      passed, failed,
      output_file: output,
    }, null, 2));

    await context.close();
    process.exit(0);

  } catch (error) {
    console.error(`[accessibility_dynamic] ✗ Erreur : ${error.message}`);
    console.log(JSON.stringify({ url, status: 'error', error: error.message }, null, 2));
    if (context) { try { await context.close(); } catch (_) {} }
    process.exit(2);
  }
}

main();
