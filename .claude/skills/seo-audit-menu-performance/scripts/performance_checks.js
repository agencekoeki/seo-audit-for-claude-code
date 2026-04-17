#!/usr/bin/env node
/**
 * performance_checks.js — Mesures Core Web Vitals réelles appliquées au menu.
 *
 * Instrumente PerformanceObserver pour capturer LCP, CLS, FCP, TTFB.
 * Simule des interactions (click burger, hover item nav) et mesure la latence
 * réelle pour estimer INP.
 *
 * Usage :
 *   node performance_checks.js --url URL --output FILE [--viewport desktop|mobile] [--profile-dir DIR]
 *
 * Codes de sortie :
 *   0 : succès
 *   2 : erreur réseau / navigation
 *   3 : erreur inattendue
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

// --- Viewports ---
const VIEWPORTS = {
  desktop: { width: 1920, height: 1080 },
  mobile: { width: 390, height: 844 },
};

const MOBILE_USER_AGENT =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 ' +
  '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

// Seuils CWV 2026
const CWV_THRESHOLDS = {
  lcp: { good: 2500, poor: 4000 },
  cls: { good: 0.1, poor: 0.25 },
  inp: { good: 200, poor: 500 },
  fcp: { good: 1800, poor: 3000 },
  ttfb: { good: 800, poor: 1800 },
};

function verdict(value, metric) {
  const t = CWV_THRESHOLDS[metric];
  if (!t) return 'UNKNOWN';
  if (value <= t.good) return 'GOOD';
  if (value <= t.poor) return 'NEEDS_IMPROVEMENT';
  return 'POOR';
}

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
  if (!args.url) { console.error('[performance_checks] ✗ --url requis'); process.exit(3); }
  if (!args.output) { console.error('[performance_checks] ✗ --output requis'); process.exit(3); }
  if (!VIEWPORTS[args.viewport]) { console.error(`[performance_checks] ✗ Viewport inconnu : ${args.viewport}`); process.exit(3); }
  return args;
}

/**
 * Instrumente la page pour capturer les métriques CWV via PerformanceObserver.
 * Retourne une fonction pour récupérer les métriques collectées.
 */
async function instrumentCWV(page) {
  await page.evaluate(() => {
    window.__cwv = { lcp: null, lcpElement: null, cls: 0, clsSources: [], fcp: null, ttfb: null };

    // LCP
    new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const last = entries[entries.length - 1];
      if (last) {
        window.__cwv.lcp = Math.round(last.startTime);
        window.__cwv.lcpElement = last.element ? last.element.tagName + (last.element.id ? '#' + last.element.id : '') + (last.element.className ? '.' + last.element.className.split(' ')[0] : '') : null;
      }
    }).observe({ type: 'largest-contentful-paint', buffered: true });

    // CLS
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) {
          window.__cwv.cls += entry.value;
          if (entry.sources) {
            for (const src of entry.sources) {
              if (src.node) {
                window.__cwv.clsSources.push({
                  element: src.node.tagName + (src.node.id ? '#' + src.node.id : ''),
                  value: entry.value,
                });
              }
            }
          }
        }
      }
    }).observe({ type: 'layout-shift', buffered: true });

    // FCP
    new PerformanceObserver((list) => {
      const entries = list.getEntries();
      if (entries.length > 0) {
        window.__cwv.fcp = Math.round(entries[0].startTime);
      }
    }).observe({ type: 'paint', buffered: true });

    // TTFB via Navigation Timing
    const navEntry = performance.getEntriesByType('navigation')[0];
    if (navEntry) {
      window.__cwv.ttfb = Math.round(navEntry.responseStart);
    }
  });
}

/**
 * Récupère les métriques CWV collectées.
 */
async function collectCWV(page) {
  return page.evaluate(() => {
    const cwv = window.__cwv || {};
    return {
      lcp_ms: cwv.lcp,
      lcp_element: cwv.lcpElement,
      cls_score: Math.round((cwv.cls || 0) * 1000) / 1000,
      cls_sources: (cwv.clsSources || []).slice(0, 5),
      fcp_ms: cwv.fcp,
      ttfb_ms: cwv.ttfb,
    };
  });
}

/**
 * Mesure la latence d'une interaction (click ou tap) sur un élément.
 * Retourne la durée en ms.
 */
async function measureInteraction(page, selector, label) {
  try {
    const el = await page.$(selector);
    if (!el) return null;
    const isVisible = await el.isVisible().catch(() => false);
    if (!isVisible) return null;

    // Injecter un observer pour la prochaine interaction
    await page.evaluate(() => {
      window.__lastInteractionDuration = null;
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.duration) {
            window.__lastInteractionDuration = Math.round(entry.duration);
          }
        }
      }).observe({ type: 'event', buffered: false, durationThreshold: 0 });
    });

    const start = await page.evaluate(() => performance.now());
    await el.click({ timeout: 3000 }).catch(() => {});
    await new Promise(r => setTimeout(r, 300));
    const end = await page.evaluate(() => performance.now());

    // Tenter de lire la durée de l'interaction via PerformanceObserver
    const observedDuration = await page.evaluate(() => window.__lastInteractionDuration);

    // Refermer avec Escape si c'était un burger/dropdown
    await page.keyboard.press('Escape').catch(() => {});
    await new Promise(r => setTimeout(r, 200));

    return {
      interaction: label,
      selector,
      duration_ms: observedDuration || Math.round(end - start),
      source: observedDuration ? 'PerformanceObserver' : 'performance.now()',
    };
  } catch (err) {
    return { interaction: label, selector, error: err.message };
  }
}

/**
 * Mesure la hauteur du header et son ratio par rapport au viewport.
 */
async function measureHeaderOccupation(page) {
  return page.evaluate(() => {
    const header = document.querySelector('header') || document.querySelector('[role="banner"]');
    if (!header) return null;
    const rect = header.getBoundingClientRect();
    return {
      header_height_px: Math.round(rect.height),
      viewport_height_px: window.innerHeight,
      ratio_percent: Math.round((rect.height / window.innerHeight) * 100),
    };
  });
}

/**
 * Détecte si le header est sticky et mesure le CLS potentiel.
 */
async function checkStickyHeader(page) {
  return page.evaluate(() => {
    const header = document.querySelector('header') || document.querySelector('[role="banner"]');
    if (!header) return { is_sticky: false };
    const style = window.getComputedStyle(header);
    const isSticky = style.position === 'sticky' || style.position === 'fixed';
    return {
      is_sticky: isSticky,
      position: style.position,
      top: style.top,
      has_transition: style.transition !== 'none' && style.transition !== '' && style.transition !== 'all 0s ease 0s',
    };
  });
}

async function main() {
  const args = parseArgs();
  const { url, output, viewport: vpName, profileDir } = args;
  const vpSize = VIEWPORTS[vpName];

  console.error(`[performance_checks] Mesures CWV pour : ${url} (viewport: ${vpName})`);

  const contextOptions = {
    headless: true,
    viewport: vpSize,
  };
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

    // Naviguer
    console.error(`[performance_checks] Navigation vers : ${url}`);
    await page.goto(url, { waitUntil: 'commit', timeout: 45000 });

    // Instrumenter CWV dès que possible
    await instrumentCWV(page);

    // Attendre le chargement complet + hydratation
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    await new Promise(r => setTimeout(r, 3000));

    // Collecter les métriques passives
    const cwv = await collectCWV(page);
    console.error(`[performance_checks]   LCP=${cwv.lcp_ms}ms, CLS=${cwv.cls_score}, FCP=${cwv.fcp_ms}ms, TTFB=${cwv.ttfb_ms}ms`);

    // --- Mesures structurelles header (avant scroll) ---
    const headerOccupation = await measureHeaderOccupation(page);
    const stickyHeader = await checkStickyHeader(page);

    // --- Mesurer INP via interactions discrètes qui NE NAVIGUENT PAS ---
    // INP = Interaction to Next Paint = click, tap, keypress. PAS scroll.
    // On reste sur la même page pour garder les PerformanceObserver actifs.
    const interactions = [];

    // Interaction 1 : cliquer sur le burger (si visible) — ne navigue pas
    const burgerSelectors = [
      'button[aria-controls*="burger" i][aria-expanded]',
      'button[aria-controls*="menu" i][aria-expanded]',
      'button[aria-controls*="drawer" i][aria-expanded]',
    ];
    for (const sel of burgerSelectors) {
      const burgerInteraction = await measureInteraction(page, sel, 'click_burger');
      if (burgerInteraction && !burgerInteraction.error) {
        interactions.push(burgerInteraction);
        break;
      }
    }

    // Interaction 2 : cliquer sur le premier item nav visible (sans naviguer)
    // On intercepte la navigation pour empêcher le changement de page
    await page.route('**/*', route => {
      if (route.request().isNavigationRequest() && route.request().url() !== url) {
        route.abort();
      } else {
        route.continue();
      }
    }).catch(() => {});
    const navItemInteraction = await measureInteraction(page, 'nav a', 'click_nav_item');
    if (navItemInteraction && !navItemInteraction.error) {
      interactions.push(navItemInteraction);
    }
    await page.unroute('**/*').catch(() => {});

    // Scroll pour déclencher le sticky header + capturer le CLS (ne compte PAS dans INP)
    await page.evaluate(() => window.scrollTo(0, 500));
    await new Promise(r => setTimeout(r, 1000));

    // INP p95 — uniquement sur les interactions discrètes avec source PerformanceObserver
    // Les mesures en fallback performance.now() ne sont pas des vrais event processing times
    const realInteractions = interactions.filter(i =>
      i && !i.error && i.source === 'PerformanceObserver' && i.duration_ms != null
    );
    const fallbackInteractions = interactions.filter(i =>
      i && !i.error && i.source === 'performance.now()'
    );
    const inp_p95 = realInteractions.length > 0
      ? Math.max(...realInteractions.map(i => i.duration_ms))
      : null;

    // --- Collecter CLS final (même session, inclut le scroll) ---
    const cwvFinal = await collectCWV(page);

    // --- Débordement horizontal mobile ---
    const horizontalOverflow = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
      overflows: document.documentElement.scrollWidth > window.innerWidth,
    }));

    // --- Images above-fold : loading lazy vs fetchpriority ---
    // Remonter en haut pour mesurer correctement
    await page.evaluate(() => window.scrollTo(0, 0));
    await new Promise(r => setTimeout(r, 300));
    const aboveFoldImages = await page.evaluate(() => {
      const vh = window.innerHeight;
      const imgs = Array.from(document.querySelectorAll('img'));
      const aboveFold = [];
      for (const img of imgs) {
        const rect = img.getBoundingClientRect();
        if (rect.top >= vh || (rect.width === 0 && rect.height === 0)) continue;
        const loading = img.getAttribute('loading');
        const fetchpriority = img.getAttribute('fetchpriority');
        aboveFold.push({
          src: (img.getAttribute('src') || '').slice(0, 120),
          in_header: !!img.closest('header'),
          loading, fetchpriority,
          width: Math.round(rect.width), height: Math.round(rect.height),
          is_lazy_above_fold: loading === 'lazy',
          has_fetchpriority: fetchpriority === 'high',
        });
      }
      return {
        test: 'above_fold_images',
        total_above_fold: aboveFold.length,
        lazy_above_fold_count: aboveFold.filter(i => i.is_lazy_above_fold).length,
        fetchpriority_high_count: aboveFold.filter(i => i.has_fetchpriority).length,
        images: aboveFold.slice(0, 10),
        severity: aboveFold.some(i => i.is_lazy_above_fold) ? 'CRITIQUE' : null,
      };
    });

    // --- Construire le résultat ---
    const missingCwv = [
      cwv.lcp_ms == null ? 'lcp' : null,
      cwvFinal.cls_score == null ? 'cls' : null,
      cwv.fcp_ms == null ? 'fcp' : null,
      cwv.ttfb_ms == null ? 'ttfb' : null,
      inp_p95 == null ? 'inp' : null,
    ].filter(Boolean);
    const perfStatus = missingCwv.length > 0 ? 'partial' : 'complete';
    const perfStatusDetail = missingCwv.length > 0 ? `Métriques manquantes : ${missingCwv.join(', ')}` : undefined;

    const result = {
      url,
      viewport: vpName,
      status: perfStatus,
      ...(perfStatusDetail ? { status_detail: perfStatusDetail } : {}),
      ttfb_ms: cwv.ttfb_ms,
      fcp_ms: cwv.fcp_ms,
      lcp_ms: cwv.lcp_ms,
      lcp_element: cwv.lcp_element,
      cls_score: cwvFinal.cls_score,
      cls_sources: cwvFinal.cls_sources,
      inp_measurements: interactions.filter(i => !i.error),
      inp_p95_ms: inp_p95,
      inp_note: inp_p95 != null
        ? `Mesuré via PerformanceObserver sur ${realInteractions.length} interaction(s)`
        : fallbackInteractions.length > 0
          ? `Aucune mesure PerformanceObserver disponible (${fallbackInteractions.length} interactions en fallback performance.now() — non fiables pour INP)`
          : 'Aucune interaction menu disponible dans ce viewport (burger non visible ?)',
      header: {
        occupation: headerOccupation,
        sticky: stickyHeader,
      },
      mobile_layout: {
        horizontal_overflow: horizontalOverflow,
      },
      above_fold_images: aboveFoldImages,
      verdict: {
        ttfb: cwv.ttfb_ms != null ? verdict(cwv.ttfb_ms, 'ttfb') : null,
        fcp: cwv.fcp_ms != null ? verdict(cwv.fcp_ms, 'fcp') : null,
        lcp: cwv.lcp_ms != null ? verdict(cwv.lcp_ms, 'lcp') : null,
        cls: verdict(cwvFinal.cls_score, 'cls'),
        inp: inp_p95 != null ? verdict(inp_p95, 'inp') : null,
      },
      checked_at: new Date().toISOString(),
    };

    // Écrire le fichier
    const outputDir = path.dirname(output);
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(output, JSON.stringify(result, null, 2), 'utf-8');

    // Résumé stderr
    console.error(`[performance_checks] ✓ Verdicts : LCP=${result.verdict.lcp}, CLS=${result.verdict.cls}, INP=${result.verdict.inp || 'N/A'}`);
    if (headerOccupation && headerOccupation.ratio_percent > 25) {
      console.error(`[performance_checks]   ⚠ Header occupe ${headerOccupation.ratio_percent}% du viewport (seuil 25%)`);
    }

    // JSON résumé stdout
    console.log(JSON.stringify({
      url,
      viewport: vpName,
      lcp_ms: cwv.lcp_ms,
      cls_score: cwvFinal.cls_score,
      inp_p95_ms: inp_p95,
      verdict: result.verdict,
      output_file: output,
    }, null, 2));

    await context.close();
    process.exit(0);

  } catch (error) {
    console.error(`[performance_checks] ✗ Erreur : ${error.message}`);
    console.log(JSON.stringify({ url, status: 'error', error: error.message }, null, 2));
    if (context) { try { await context.close(); } catch (_) {} }
    process.exit(2);
  }
}

main();
