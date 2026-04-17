#!/usr/bin/env node
/**
 * viewport_content_parity.js — Compare les blocs de texte visibles entre desktop et mobile.
 *
 * Détecte les contenus visibles dans un viewport mais masqués dans l'autre
 * (ex: responsive CSS via Tailwind lg:hidden, media queries min-width, etc.).
 * Qualifie chaque écart : mots-clés de positionnement ? volume de texte ?
 * liens de navigation ?
 *
 * Usage :
 *   node viewport_content_parity.js --url URL --output FILE [--profile-dir DIR]
 *
 * Codes de sortie :
 *   0 : succès
 *   2 : erreur réseau / navigation
 *   3 : erreur inattendue
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

// Mots-clés signalant un contenu de positionnement SEO
const POSITIONING_KEYWORDS = [
  'n°1', 'numéro 1', 'leader', '+ de', 'plus de',
  'meilleur', 'premier', '# 1', 'first', 'top',
  '#1', 'number one', 'best', 'leading',
];

// --- Viewports ---
const VIEWPORTS = {
  desktop: { width: 1920, height: 1080 },
  mobile: { width: 390, height: 844 },
};

const MOBILE_USER_AGENT =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 ' +
  '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

/**
 * Capture les blocs de texte visibles dans la page.
 * Retourne un tableau d'objets { text, visible, tag, wordCount, hasLinks, linkCount }.
 */
async function captureVisibleBlocks(page) {
  return page.evaluate(() => {
    const candidates = document.querySelectorAll(
      'h1, h2, h3, h4, h5, h6, p, li, span, div, strong, em, figcaption, blockquote'
    );
    const blocks = [];
    const seen = new Set();

    for (const el of candidates) {
      const text = (el.textContent || '').trim();
      if (text.length < 15) continue;
      // Éviter les containers larges qui englobent tout
      if (el.children.length > 3) continue;
      // Filtrer les blocs trop longs (containers avec textContent des descendants)
      if (text.length > 500) continue;
      // Éviter les doublons (un enfant et son parent avec le même texte)
      if (seen.has(text)) continue;
      seen.add(text);

      // Vérifier la visibilité via checkVisibility (API moderne) ou fallback
      let visible;
      if (typeof el.checkVisibility === 'function') {
        visible = el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true });
      } else {
        const style = window.getComputedStyle(el);
        visible = style.display !== 'none' && style.visibility !== 'hidden' &&
                  style.opacity !== '0' && el.offsetWidth > 0 && el.offsetHeight > 0;
      }

      // Compter les liens à l'intérieur
      const links = el.querySelectorAll('a[href]');

      blocks.push({
        text: text.slice(0, 300),
        visible,
        tag: el.tagName.toLowerCase(),
        wordCount: text.split(/\s+/).filter(w => w.length > 0).length,
        hasLinks: links.length > 0,
        linkCount: links.length,
      });
    }
    return blocks;
  });
}

/**
 * Vérifie si un texte contient des mots-clés de positionnement.
 */
function isPositioningBlock(text) {
  const lower = text.toLowerCase();
  return POSITIONING_KEYWORDS.some(kw => lower.includes(kw));
}

/**
 * Normalise un texte pour la comparaison : lowercase, espaces condensés, ponctuation retirée.
 */
function normalizeText(text) {
  return text.toLowerCase().replace(/[^\w\sàâäéèêëïîôùûüÿçœæ]/g, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * Calcule la similarité de mots entre deux textes (Jaccard sur les mots).
 * Retourne un ratio entre 0 et 1.
 */
function wordSimilarity(textA, textB) {
  const wordsA = new Set(normalizeText(textA).split(' ').filter(w => w.length > 2));
  const wordsB = new Set(normalizeText(textB).split(' ').filter(w => w.length > 2));
  if (wordsA.size === 0 && wordsB.size === 0) return 1;
  const intersection = new Set([...wordsA].filter(w => wordsB.has(w)));
  const union = new Set([...wordsA, ...wordsB]);
  return union.size > 0 ? intersection.size / union.size : 0;
}

/**
 * Vérifie si un texte est un sous-ensemble d'un autre (variante responsive raccourcie).
 * Ex: "Donner un avis" est un sous-ensemble de "Patient, donner un avis".
 */
function isSubsetVariant(shortText, longText) {
  const shortNorm = normalizeText(shortText);
  const longNorm = normalizeText(longText);
  return longNorm.includes(shortNorm) || shortNorm.includes(longNorm);
}

/**
 * Cherche une variante responsive d'un texte dans l'autre viewport.
 * Ne compare qu'avec des blocs de taille comparable (ratio max 3x)
 * pour éviter les faux positifs avec les méga-containers.
 * Retourne le texte correspondant ou null.
 */
function findResponsiveVariant(text, otherViewportMap) {
  const SIMILARITY_THRESHOLD = 0.6;
  const MAX_LENGTH_RATIO = 3;
  const textLen = text.length;

  for (const [otherText] of otherViewportMap) {
    // Filtrer les blocs de taille trop différente (pas une variante, c'est un container)
    const otherLen = otherText.length;
    const ratio = textLen > otherLen ? textLen / otherLen : otherLen / textLen;
    if (ratio > MAX_LENGTH_RATIO) continue;

    if (isSubsetVariant(text, otherText)) return otherText;
    if (wordSimilarity(text, otherText) >= SIMILARITY_THRESHOLD) return otherText;
  }
  return null;
}

/**
 * Parse les arguments CLI.
 */
function parseArgs() {
  const args = { url: null, output: null, profileDir: null };
  const argv = process.argv.slice(2);

  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case '--url':
        args.url = argv[++i];
        break;
      case '--output':
        args.output = argv[++i];
        break;
      case '--profile-dir':
        args.profileDir = argv[++i];
        break;
    }
  }

  if (!args.url) {
    console.error('[viewport_content_parity] ✗ Argument --url requis');
    process.exit(3);
  }
  if (!args.output) {
    console.error('[viewport_content_parity] ✗ Argument --output requis');
    process.exit(3);
  }

  return args;
}

/**
 * Capture les blocs dans un viewport donné.
 */
async function captureForViewport(url, vpName, vpSize, profileDir) {
  const contextOptions = {
    headless: true,  // Pas besoin de fenêtre visible pour ce test
    viewport: vpSize,
  };
  if (vpName === 'mobile') {
    contextOptions.userAgent = MOBILE_USER_AGENT;
    contextOptions.isMobile = true;
    contextOptions.hasTouch = true;
  }

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
    await new Promise(r => setTimeout(r, 3000)); // Hydratation JS
    const blocks = await captureVisibleBlocks(page);

    // Compter les liens internes visibles
    const internalLinksCount = await page.evaluate(() => {
      const hostname = window.location.hostname;
      return Array.from(document.querySelectorAll('a[href]'))
        .filter(a => {
          try {
            const url = new URL(a.href, window.location.origin);
            if (url.hostname !== hostname) return false;
          } catch (_) { return false; }
          if (typeof a.checkVisibility === 'function') return a.checkVisibility();
          return a.offsetWidth > 0 && a.offsetHeight > 0;
        }).length;
    });

    // Capturer les meta tags pour la parité
    const metaTags = await page.evaluate(() => {
      const getMeta = (name) => {
        const el = document.querySelector(`meta[name="${name}"]`);
        return el ? el.getAttribute('content') : null;
      };
      const getLink = (rel) => {
        const el = document.querySelector(`link[rel="${rel}"]`);
        return el ? el.getAttribute('href') : null;
      };
      return {
        title: document.title || '',
        description: getMeta('description'),
        robots: getMeta('robots'),
        googlebot: getMeta('googlebot'),
        canonical: getLink('canonical'),
      };
    });

    // Capturer les ancres nav visibles
    const navAnchors = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('nav a[href]'))
        .filter(a => {
          if (typeof a.checkVisibility === 'function') return a.checkVisibility();
          return a.offsetWidth > 0 && a.offsetHeight > 0;
        })
        .map(a => ({ href: a.href, text: (a.textContent || '').trim() }));
    });

    // Capturer TOUS les liens nav (DOM + visibilité) pour diff A2
    const navLinksAll = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('nav a[href]')).map(a => {
        let visible;
        if (typeof a.checkVisibility === 'function') {
          visible = a.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true });
        } else {
          const s = window.getComputedStyle(a);
          visible = s.display !== 'none' && s.visibility !== 'hidden' &&
                    s.opacity !== '0' && a.offsetWidth > 0;
        }
        return {
          href: a.href,
          text: (a.textContent || '').trim().slice(0, 100),
          in_dom: true,
          visible,
        };
      });
    });

    // Capturer JSON-LD
    const jsonLd = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('script[type="application/ld+json"]')).map(s => {
        try { return JSON.parse(s.textContent); } catch { return { _parse_error: true }; }
      });
    });

    return { blocks, internalLinksCount, metaTags, navAnchors, navLinksAll, jsonLd };
  } finally {
    await context.close();
  }
}

async function main() {
  const args = parseArgs();
  const { url, output, profileDir } = args;

  console.error(`[viewport_content_parity] Analyse de la parité desktop/mobile pour : ${url}`);

  try {
    // Capturer les deux viewports
    console.error('[viewport_content_parity] Capture desktop (1920x1080)...');
    const desktopData = await captureForViewport(url, 'desktop', VIEWPORTS.desktop, profileDir);

    console.error('[viewport_content_parity] Capture mobile (390x844)...');
    const mobileData = await captureForViewport(url, 'mobile', VIEWPORTS.mobile, profileDir);

    // Construire les maps de blocs visibles
    const desktopVisible = new Map();
    for (const b of desktopData.blocks) {
      if (b.visible) desktopVisible.set(b.text, b);
    }
    const mobileVisible = new Map();
    for (const b of mobileData.blocks) {
      if (b.visible) mobileVisible.set(b.text, b);
    }

    // Détecter les mismatches
    const mismatches = [];

    for (const [text, block] of desktopVisible) {
      if (!mobileVisible.has(text)) {
        // Chercher une variante responsive (texte raccourci/reformulé)
        const variant = findResponsiveVariant(text, mobileVisible);
        const isVariant = variant !== null;

        const positioning = isPositioningBlock(text);
        let severity;
        if (isVariant) severity = 'RECOMMANDATION';
        else if (positioning) severity = 'CRITIQUE';
        else if (block.hasLinks) severity = 'IMPORTANT';
        else if (block.wordCount > 50) severity = 'IMPORTANT';
        else severity = 'RECOMMANDATION';

        mismatches.push({
          type: 'visible_desktop_hidden_mobile',
          text,
          tag: block.tag,
          word_count: block.wordCount,
          has_links: block.hasLinks,
          link_count: block.linkCount,
          is_positioning: positioning,
          is_responsive_variant: isVariant,
          responsive_variant_of: variant,
          severity,
        });
      }
    }

    for (const [text, block] of mobileVisible) {
      if (!desktopVisible.has(text)) {
        const variant = findResponsiveVariant(text, desktopVisible);
        const isVariant = variant !== null;

        const positioning = isPositioningBlock(text);
        mismatches.push({
          type: 'visible_mobile_hidden_desktop',
          text,
          tag: block.tag,
          word_count: block.wordCount,
          has_links: block.hasLinks,
          link_count: block.linkCount,
          is_positioning: positioning,
          is_responsive_variant: isVariant,
          responsive_variant_of: variant,
          severity: isVariant ? 'RECOMMANDATION' : (positioning ? 'CRITIQUE' : 'RECOMMANDATION'),
        });
      }
    }

    // --- Diff liens nav : DOM + visibilité par viewport (A2) ---
    const desktopNavHrefs = new Map(desktopData.navLinksAll.map(l => [l.href, l]));
    const mobileNavHrefs = new Map(mobileData.navLinksAll.map(l => [l.href, l]));

    const linksVisibleDesktopHiddenMobile = [];
    const linksAbsentMobileDom = [];
    const linksVisibleMobileHiddenDesktop = [];

    for (const [href, dLink] of desktopNavHrefs) {
      const mLink = mobileNavHrefs.get(href);
      if (!mLink) {
        linksAbsentMobileDom.push({
          href, text: dLink.text, severity: 'CRITIQUE',
          reason: 'Lien absent du DOM mobile. Googlebot Smartphone ne le voit pas du tout.',
        });
      } else if (dLink.visible && !mLink.visible) {
        linksVisibleDesktopHiddenMobile.push({
          href, text: dLink.text, severity: 'IMPORTANT',
          reason: 'Lien dans le DOM mobile mais invisible (display:none). Googlebot le voit mais avec moins de poids.',
        });
      }
    }
    for (const [href, mLink] of mobileNavHrefs) {
      const dLink = desktopNavHrefs.get(href);
      if (dLink && !dLink.visible && mLink.visible) {
        linksVisibleMobileHiddenDesktop.push({ href, text: mLink.text, severity: 'RECOMMANDATION' });
      }
    }

    const navLinksParity = {
      desktop_total: desktopData.navLinksAll.length,
      desktop_visible: desktopData.navLinksAll.filter(l => l.visible).length,
      mobile_total: mobileData.navLinksAll.length,
      mobile_visible: mobileData.navLinksAll.filter(l => l.visible).length,
      links_visible_desktop_hidden_mobile: linksVisibleDesktopHiddenMobile,
      links_absent_mobile_dom: linksAbsentMobileDom,
      links_visible_mobile_hidden_desktop: linksVisibleMobileHiddenDesktop,
    };

    // --- Diff JSON-LD par viewport (A5) ---
    const getTypes = (arr) => arr.filter(j => !j._parse_error).map(j => j['@type']).filter(Boolean);
    const desktopTypes = getTypes(desktopData.jsonLd);
    const mobileTypes = getTypes(mobileData.jsonLd);
    const missingInMobile = desktopTypes.filter(t => !mobileTypes.includes(t));
    const missingInDesktop = mobileTypes.filter(t => !desktopTypes.includes(t));

    const jsonldParity = {
      desktop_count: desktopData.jsonLd.length,
      mobile_count: mobileData.jsonLd.length,
      types_desktop: desktopTypes,
      types_mobile: mobileTypes,
      missing_in_mobile: missingInMobile,
      missing_in_desktop: missingInDesktop,
    };

    // --- Diff ancres nav par viewport ---
    const desktopAnchorMap = new Map(desktopData.navAnchors.map(a => [a.href, a.text]));
    const mobileAnchorMap = new Map(mobileData.navAnchors.map(a => [a.href, a.text]));
    const navAnchorDiffs = [];
    for (const [href, desktopText] of desktopAnchorMap) {
      const mobileText = mobileAnchorMap.get(href);
      if (mobileText === undefined || mobileText === desktopText) continue;
      const desktopWords = new Set(desktopText.toLowerCase().split(/\s+/).filter(w => w.length > 2));
      const mobileWords = new Set(mobileText.toLowerCase().split(/\s+/).filter(w => w.length > 2));
      const lostWords = [...desktopWords].filter(w => !mobileWords.has(w));
      navAnchorDiffs.push({
        href,
        desktop_text: desktopText,
        mobile_text: mobileText,
        lost_words: lostWords,
        severity: lostWords.length > 0 ? 'IMPORTANT' : 'RECOMMANDATION',
      });
    }

    // --- Parité meta tags ---
    const metaParityIssues = [];
    const metaFields = [
      { tag: 'robots', severity: 'BLOQUANT' },
      { tag: 'googlebot', severity: 'BLOQUANT' },
      { tag: 'canonical', severity: 'CRITIQUE' },
      { tag: 'title', severity: 'IMPORTANT' },
      { tag: 'description', severity: 'RECOMMANDATION' },
    ];
    for (const { tag, severity } of metaFields) {
      const dVal = desktopData.metaTags[tag];
      const mVal = mobileData.metaTags[tag];
      if (dVal !== mVal) {
        metaParityIssues.push({ tag, desktop_value: dVal, mobile_value: mVal, severity });
      }
    }
    const metaParity = {
      title_match: desktopData.metaTags.title === mobileData.metaTags.title,
      description_match: desktopData.metaTags.description === mobileData.metaTags.description,
      robots_match: desktopData.metaTags.robots === mobileData.metaTags.robots,
      canonical_match: desktopData.metaTags.canonical === mobileData.metaTags.canonical,
      issues: metaParityIssues,
    };

    // Liens internes
    const internalLinksDiff = desktopData.internalLinksCount - mobileData.internalLinksCount;
    const internalLinksDiffPercent = desktopData.internalLinksCount > 0
      ? Math.round((internalLinksDiff / desktopData.internalLinksCount) * 100)
      : 0;

    // Résultat
    const result = {
      url,
      status: 'complete',
      desktop_visible_blocks: desktopVisible.size,
      mobile_visible_blocks: mobileVisible.size,
      mismatches_count: mismatches.length,
      mismatches,
      desktop_internal_links_count: desktopData.internalLinksCount,
      mobile_internal_links_count: mobileData.internalLinksCount,
      internal_links_diff: internalLinksDiff,
      internal_links_diff_percent: internalLinksDiffPercent,
      meta_parity: metaParity,
      nav_links_parity: navLinksParity,
      jsonld_parity: jsonldParity,
      nav_anchor_diffs: navAnchorDiffs,
      checked_at: new Date().toISOString(),
    };

    // Écrire le fichier de sortie
    const outputDir = path.dirname(output);
    fs.mkdirSync(outputDir, { recursive: true });
    fs.writeFileSync(output, JSON.stringify(result, null, 2), 'utf-8');

    // Résumé sur stderr
    const critiques = mismatches.filter(m => m.severity === 'CRITIQUE').length;
    const importants = mismatches.filter(m => m.severity === 'IMPORTANT').length;
    console.error(
      `[viewport_content_parity] ✓ ${mismatches.length} écart(s) détecté(s) ` +
      `(${critiques} CRITIQUE, ${importants} IMPORTANT). Résultat : ${output}`
    );

    // JSON résumé sur stdout (pour consommation par les agents)
    const summary = {
      url,
      mismatches_count: mismatches.length,
      critiques,
      importants,
      output_file: output,
    };
    console.log(JSON.stringify(summary, null, 2));

    process.exit(0);

  } catch (error) {
    console.error(`[viewport_content_parity] ✗ Erreur : ${error.message}`);
    const result = {
      url,
      status: 'error',
      error: error.message,
      checked_at: new Date().toISOString(),
    };
    console.log(JSON.stringify(result, null, 2));
    process.exit(2);
  }
}

main();
