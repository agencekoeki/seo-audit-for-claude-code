#!/usr/bin/env node
/**
 * fetch_googlebot.js — Fetch une URL avec User-Agent Googlebot Smartphone.
 *
 * Compare le HTML reçu par Googlebot avec celui reçu par un navigateur standard.
 * Détecte un éventuel cloaking ou adaptive serving défaillant.
 *
 * Usage :
 *   node fetch_googlebot.js --url URL --output FILE [--profile-dir DIR]
 *
 * Codes de sortie :
 *   0 : succès
 *   2 : erreur réseau
 *   3 : erreur inattendue
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const GOOGLEBOT_UA =
  'Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/125.0.6422.175 Mobile Safari/537.36 ' +
  '(compatible; Googlebot/2.1; +http://www.google.com/bot.html)';

const STANDARD_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36';

const VIEWPORT_MOBILE = { width: 412, height: 915 };

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
  if (!args.url) { console.error('[fetch_googlebot] ✗ --url requis'); process.exit(3); }
  if (!args.output) { console.error('[fetch_googlebot] ✗ --output requis'); process.exit(3); }
  return args;
}

/**
 * Fetch une URL avec un UA donné, retourne le HTML et les liens nav.
 */
async function fetchWithUA(url, userAgent, label, profileDir) {
  const contextOptions = {
    headless: true,
    viewport: VIEWPORT_MOBILE,
    userAgent,
    isMobile: true,
  };

  let context;
  if (profileDir) {
    context = await chromium.launchPersistentContext(profileDir, contextOptions);
  } else {
    const browser = await chromium.launch({ headless: true });
    context = await browser.newContext(contextOptions);
  }

  const page = context.pages()[0] || await context.newPage();

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
    await new Promise(r => setTimeout(r, 3000));

    const html = await page.content();
    const navLinks = await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('nav a[href]'));
      return links.map(a => ({ href: a.href, text: (a.textContent || '').trim().slice(0, 100) }));
    });
    const title = await page.title();

    return { html, navLinks, title, htmlLength: html.length };
  } finally {
    await context.close();
  }
}

/**
 * Compare deux ensembles de liens nav.
 */
function diffNavLinks(standardLinks, googlebotLinks) {
  const standardUrls = new Set(standardLinks.map(l => l.href));
  const googlebotUrls = new Set(googlebotLinks.map(l => l.href));

  const onlyInStandard = standardLinks.filter(l => !googlebotUrls.has(l.href));
  const onlyInGooglebot = googlebotLinks.filter(l => !standardUrls.has(l.href));

  return { onlyInStandard, onlyInGooglebot };
}

async function main() {
  const args = parseArgs();
  const { url, output, profileDir } = args;

  console.error(`[fetch_googlebot] Test cloaking pour : ${url}`);

  try {
    // Fetch avec UA standard
    console.error('[fetch_googlebot] Fetch avec UA Chrome standard...');
    const standard = await fetchWithUA(url, STANDARD_UA, 'standard', profileDir);

    // Fetch avec UA Googlebot
    console.error('[fetch_googlebot] Fetch avec UA Googlebot Smartphone...');
    const googlebot = await fetchWithUA(url, GOOGLEBOT_UA, 'googlebot', profileDir);

    // Comparer
    const diff = diffNavLinks(standard.navLinks, googlebot.navLinks);
    const htmlLengthDiff = Math.abs(standard.htmlLength - googlebot.htmlLength);
    const htmlLengthRatio = standard.htmlLength > 0
      ? Math.round((htmlLengthDiff / standard.htmlLength) * 100)
      : 0;

    const titleMatch = standard.title === googlebot.title;
    const navLinksMatch = diff.onlyInStandard.length === 0 && diff.onlyInGooglebot.length === 0;

    // Détecter le cloaking
    let cloakingDetected = false;
    let severity = null;
    const issues = [];

    if (!titleMatch) {
      issues.push(`Titre différent : standard="${standard.title}" vs googlebot="${googlebot.title}"`);
    }
    if (htmlLengthRatio > 30) {
      issues.push(`Taille HTML diverge de ${htmlLengthRatio}% (${standard.htmlLength} vs ${googlebot.htmlLength} chars)`);
      cloakingDetected = true;
      severity = 'CRITIQUE';
    }
    if (!navLinksMatch) {
      const missing = diff.onlyInStandard.length;
      const extra = diff.onlyInGooglebot.length;
      issues.push(`Nav links divergent : ${missing} absents pour Googlebot, ${extra} supplémentaires pour Googlebot`);
      if (missing > 0) {
        cloakingDetected = true;
        severity = 'CRITIQUE';
      }
    }

    const result = {
      url,
      standard: {
        user_agent: STANDARD_UA.slice(0, 50) + '...',
        html_length: standard.htmlLength,
        nav_links_count: standard.navLinks.length,
        title: standard.title,
      },
      googlebot: {
        user_agent: GOOGLEBOT_UA.slice(0, 50) + '...',
        html_length: googlebot.htmlLength,
        nav_links_count: googlebot.navLinks.length,
        title: googlebot.title,
      },
      comparison: {
        title_match: titleMatch,
        nav_links_match: navLinksMatch,
        html_length_diff_percent: htmlLengthRatio,
        nav_only_in_standard: diff.onlyInStandard.slice(0, 10),
        nav_only_in_googlebot: diff.onlyInGooglebot.slice(0, 10),
      },
      cloaking_detected: cloakingDetected,
      issues,
      severity,
      checked_at: new Date().toISOString(),
    };

    // Écrire le résultat
    const outputDir = path.dirname(output);
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(output, JSON.stringify(result, null, 2), 'utf-8');

    if (cloakingDetected) {
      console.error(`[fetch_googlebot] ⚠ CLOAKING POTENTIEL DÉTECTÉ — ${issues.length} divergence(s)`);
    } else {
      console.error('[fetch_googlebot] ✓ Pas de cloaking détecté.');
    }

    console.log(JSON.stringify({
      url,
      cloaking_detected: cloakingDetected,
      issues_count: issues.length,
      output_file: output,
    }, null, 2));

    process.exit(0);

  } catch (error) {
    console.error(`[fetch_googlebot] ✗ Erreur : ${error.message}`);
    console.log(JSON.stringify({ url, error: error.message }, null, 2));
    process.exit(2);
  }
}

main();
