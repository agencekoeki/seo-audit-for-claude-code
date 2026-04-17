#!/usr/bin/env node
/**
 * test_burger_radix.js — Test d'intégration pour le diff DOM burger sur un site Radix.
 *
 * Charge la fixture radix_burger_portal.html via Playwright, exécute la logique
 * de captureBurgerPanels, et vérifie que les liens injectés par le portail React
 * sont bien capturés même si l'id du panneau ne correspond pas à aria-controls.
 *
 * Usage :
 *   node tests/integration/test_burger_radix.js
 *
 * Code de sortie :
 *   0 : tous les tests passent
 *   1 : au moins un test échoue
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const FIXTURE_PATH = path.resolve(__dirname, '..', 'fixtures', 'radix_burger_portal.html');

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  ✓ ${message}`);
    passed++;
  } else {
    console.error(`  ✗ FAIL: ${message}`);
    failed++;
  }
}

/**
 * Copie de collectAllLinks depuis fetch_authenticated.js
 * (on ne peut pas require le script car il appelle main() au chargement)
 */
async function collectAllLinks(page) {
  return page.evaluate(() => {
    return Array.from(document.querySelectorAll('a[href]')).map(a => ({
      href: a.href,
      text: (a.textContent || '').trim().slice(0, 200),
    }));
  });
}

async function main() {
  console.log('=== Test intégration : burger Radix portal ===\n');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();

  // Charger la fixture
  const fileUrl = `file://${FIXTURE_PATH.replace(/\\/g, '/')}`;
  await page.goto(fileUrl, { waitUntil: 'load' });

  // --- Test 1 : le bouton burger est détecté ---
  console.log('Test 1 — Détection du bouton burger');
  const burgerBtn = await page.$('button[aria-expanded][aria-controls]');
  assert(burgerBtn !== null, 'Bouton burger trouvé dans le DOM');

  const ariaExpanded = await burgerBtn.getAttribute('aria-expanded');
  assert(ariaExpanded === 'false', 'aria-expanded="false" avant clic');

  const ariaControls = await burgerBtn.getAttribute('aria-controls');
  assert(ariaControls === 'radix-:R1:', `aria-controls="${ariaControls}"`);

  // --- Test 2 : pas de panneau dans le DOM avant clic ---
  console.log('\nTest 2 — Pas de panneau portal avant clic');
  // Le sélecteur CSS #radix-:R1: crashe (caractères : non échappés dans les ids Radix)
  // C'est exactement le problème qui justifie l'approche diff DOM
  let panelBefore = null;
  try {
    panelBefore = await page.$(`#${CSS.escape(ariaControls)}`);
  } catch (_) {
    // CSS.escape n'est pas dispo côté Node, fallback
    panelBefore = await page.evaluate((id) => document.getElementById(id), ariaControls);
  }
  assert(panelBefore === null, 'Panneau #radix-:R1: absent avant clic (portail non injecté)');

  // --- Test 3 : diff DOM capture les liens injectés ---
  console.log('\nTest 3 — Diff DOM capture les liens du portail');
  const linksBefore = await collectAllLinks(page);
  const hrefSetBefore = new Set(linksBefore.map(l => l.href));

  await burgerBtn.click();
  await new Promise(r => setTimeout(r, 500));

  const linksAfter = await collectAllLinks(page);
  const injectedLinks = linksAfter.filter(l => !hrefSetBefore.has(l.href));

  assert(injectedLinks.length > 0, `Diff DOM a détecté ${injectedLinks.length} lien(s) injecté(s)`);

  // /medecins et /specialites sont UNIQUEMENT dans le burger, pas dans le nav desktop
  const hasNouvelleUrl = injectedLinks.some(l => l.href.includes('/medecins'));
  assert(hasNouvelleUrl, '/medecins détecté comme lien injecté par le burger');

  const hasSpecialites = injectedLinks.some(l => l.href.includes('/specialites'));
  assert(hasSpecialites, '/specialites détecté comme lien injecté par le burger');

  // /login aussi
  const hasLogin = injectedLinks.some(l => l.href.includes('/login'));
  assert(hasLogin, '/login détecté comme lien injecté par le burger');

  // --- Test 4 : limitation connue — /etablissements est dans le footer ET le burger ---
  console.log('\nTest 4 — Limitation diff DOM : lien dupliqué footer+burger');
  const hasEtablissements = injectedLinks.some(l => l.href.includes('/etablissements'));
  // Ce test DEVRAIT être false (limitation connue documentée dans SKILL.md)
  assert(!hasEtablissements, '/etablissements NOT dans le diff (présent dans le footer = limitation connue du diff DOM)');

  // --- Test 5 : Escape ferme et aria-expanded revient à false ---
  console.log('\nTest 5 — Escape ferme le burger');
  await page.keyboard.press('Escape');
  await new Promise(r => setTimeout(r, 300));
  const ariaExpandedAfterEsc = await burgerBtn.getAttribute('aria-expanded');
  assert(ariaExpandedAfterEsc === 'false', 'aria-expanded="false" après Escape');

  // Le portail doit avoir été retiré
  const sheetAfterEsc = await page.$('.radix-sheet');
  assert(sheetAfterEsc === null, 'Portail Radix retiré du DOM après Escape');

  // --- Résultat ---
  await browser.close();

  console.log(`\n=== Résultat : ${passed} passé(s), ${failed} échoué(s) ===`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => {
  console.error(`Erreur fatale : ${err.message}`);
  process.exit(1);
});
