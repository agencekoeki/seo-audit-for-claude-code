#!/usr/bin/env node
/**
 * interstitial_checker.js — Détecte les interstitiels intrusifs en viewport mobile.
 *
 * Au chargement, identifie les éléments fixed/absolute avec z-index élevé
 * qui couvrent >30% du viewport. Exclut les headers/nav et qualifie les
 * cookie banners comme non-intrusifs.
 *
 * Usage :
 *   node interstitial_checker.js --url URL --output FILE [--profile-dir DIR]
 *
 * Codes de sortie :
 *   0 : succès
 *   2 : erreur réseau
 *   3 : erreur inattendue
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const MOBILE_VIEWPORT = { width: 390, height: 844 };
const MOBILE_USER_AGENT =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 ' +
  '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

function parseArgs() {
  const args = { url: null, output: null, profileDir: null };
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case '--url': args.url = argv[++i]; break;
      case '--output': args.output = argv[++i]; break;
      case '--profile-dir': args.profileDir = argv[++i]; break;
    }
  }
  if (!args.url) { console.error('[interstitial_checker] ✗ --url requis'); process.exit(3); }
  if (!args.output) { console.error('[interstitial_checker] ✗ --output requis'); process.exit(3); }
  return args;
}

async function detectInterstitials(page) {
  return page.evaluate(() => {
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const viewportArea = vh * vw;
    const interstitials = [];
    let candidatesScanned = 0;

    for (const el of document.querySelectorAll('*')) {
      const style = window.getComputedStyle(el);
      if (style.position !== 'fixed' && style.position !== 'absolute') continue;
      if (style.display === 'none' || style.visibility === 'hidden') continue;

      const zIndex = parseInt(style.zIndex) || 0;
      if (zIndex < 10) continue;

      candidatesScanned++;

      const rect = el.getBoundingClientRect();
      const area = rect.width * rect.height;
      const coveragePercent = Math.round((area / viewportArea) * 100);
      if (coveragePercent < 30) continue;

      const tag = el.tagName.toLowerCase();
      if (tag === 'header' || tag === 'nav') continue;
      const role = el.getAttribute('role') || '';
      if (role === 'banner' || role === 'navigation') continue;

      const classId = ((el.className || '') + ' ' + (el.id || '')).toLowerCase();
      const isCookieBanner = /cookie|consent|gdpr|privacy|rgpd|tarteaucitron/.test(classId);

      interstitials.push({
        tag,
        id: el.id || null,
        class: (el.className || '').toString().slice(0, 80),
        z_index: zIndex,
        coverage_percent: coveragePercent,
        is_cookie_banner: isCookieBanner,
        is_intrusive: !isCookieBanner && coveragePercent > 30,
      });
    }

    return { interstitials, candidates_scanned: candidatesScanned };
  });
}

async function main() {
  const args = parseArgs();
  const { url, output, profileDir } = args;

  console.error(`[interstitial_checker] Détection interstitiels mobile pour : ${url}`);

  const contextOptions = {
    headless: true,
    viewport: MOBILE_VIEWPORT,
    userAgent: MOBILE_USER_AGENT,
    isMobile: true,
    hasTouch: true,
  };

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

    const detection = await detectInterstitials(page);
    const interstitials = detection.interstitials;
    const intrusive = interstitials.filter(i => i.is_intrusive);
    const cookies = interstitials.filter(i => i.is_cookie_banner);

    const result = {
      url,
      viewport: 'mobile',
      status: 'complete',
      elements_scanned: detection.candidates_scanned,
      interstitials_detected: interstitials.length,
      intrusive_interstitials: intrusive.length,
      cookie_banners: cookies.length,
      details: interstitials,
      severity: intrusive.length > 0 ? 'CRITIQUE' : null,
      checked_at: new Date().toISOString(),
    };

    const outputDir = path.dirname(output);
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(output, JSON.stringify(result, null, 2), 'utf-8');

    if (intrusive.length > 0) {
      console.error(`[interstitial_checker] ⚠ ${intrusive.length} interstitiel(s) intrusif(s) détecté(s)`);
    } else {
      console.error(`[interstitial_checker] ✓ Pas d'interstitiel intrusif. ${cookies.length} cookie banner(s).`);
    }

    console.log(JSON.stringify({
      url,
      intrusive: intrusive.length,
      cookie_banners: cookies.length,
      severity: result.severity,
      output_file: output,
    }, null, 2));

    await context.close();
    process.exit(0);

  } catch (error) {
    console.error(`[interstitial_checker] ✗ Erreur : ${error.message}`);
    console.log(JSON.stringify({ url, status: 'error', error: error.message }, null, 2));
    if (context) { try { await context.close(); } catch (_) {} }
    process.exit(2);
  }
}

main();
