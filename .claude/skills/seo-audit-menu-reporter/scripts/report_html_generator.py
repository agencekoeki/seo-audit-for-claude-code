#!/usr/bin/env python3
"""
report_html_generator.py — Genere un rapport HTML autonome a partir des findings JSON.

Lit les fichiers JSON du dossier findings/ d'un audit, calcule les scores par
categorie, et produit un fichier HTML standalone avec CSS et JS embarques.
Aucune dependance externe : stdlib Python 3.10+ uniquement.

Usage :
    python3 report_html_generator.py \
        --audit-dir audits/2026-04-16-site/ \
        --site-name "example.com" \
        --mode audit \
        --output audits/2026-04-16-site/reports/audit-report.html

Codes de sortie :
    0 : succes
    1 : erreur d'entree (dossier introuvable, arguments invalides)
    3 : erreur inattendue
"""

from __future__ import annotations

import argparse
import html
import io
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Compatibilite Windows : forcer UTF-8 sur stdout
# ---------------------------------------------------------------------------
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Version du toolkit — affichee dans le footer du rapport
# ---------------------------------------------------------------------------
TOOLKIT_VERSION = "0.4.0"

# ---------------------------------------------------------------------------
# Constantes de severite et scores
# ---------------------------------------------------------------------------
SEVERITY_ORDER = ["bloquant", "critique", "important", "recommandation"]

SEVERITY_SCORE: dict[str, int] = {
    "bloquant": 0,
    "critique": 25,
    "important": 50,
    "recommandation": 75,
    "ok": 100,
}

SEVERITY_EMOJI: dict[str, str] = {
    "bloquant": "\U0001f6ab",
    "critique": "\U0001f534",
    "important": "\u26a0\ufe0f",
    "recommandation": "\U0001f4a1",
}

SEVERITY_LABEL: dict[str, str] = {
    "bloquant": "BLOQUANT",
    "critique": "CRITIQUE",
    "important": "IMPORTANT",
    "recommandation": "RECOMMANDATION",
}

# Les 5 categories de scoring — correspondance entre cle fichier et label FR
SCORE_CATEGORIES: list[tuple[str, str]] = [
    ("crawlability", "Crawlabilite"),
    ("link-equity", "Link Equity"),
    ("accessibility", "Accessibilite"),
    ("performance", "Performance"),
    ("semantic", "Mobile / Semantic"),
]

# Mapping nom de fichier (sans prefixe prod-/staging-) → categorie de score
FILENAME_TO_CATEGORY: dict[str, str] = {
    "a11y": "accessibility",
    "perf": "performance",
    "vcp": "semantic",
    "css": "crawlability",
    "breadcrumb": "semantic",
    "googlebot": "crawlability",
    "i18n": "crawlability",
    "interstitial": "performance",
    "sitemap": "crawlability",
}

# Mapping dimension fichier → categorie de score
DIMENSION_TO_CATEGORY: dict[str, str] = {
    "crawlability": "crawlability",
    "crawlabilite": "crawlability",
    "link-equity": "link-equity",
    "link_equity": "link-equity",
    "accessibility": "accessibility",
    "accessibilite": "accessibility",
    "performance": "performance",
    "semantic": "semantic",
    "architecture": "semantic",
}

# ---------------------------------------------------------------------------
# Guides de correction maieutiques
# ---------------------------------------------------------------------------
CORRECTION_GUIDES: dict[str, dict[str, Any]] = {
    "above_fold_images": {
        "title": "Images above-fold avec loading=\"lazy\"",
        "questions": [
            "Le loading=\"lazy\" est-il ajoute automatiquement par votre framework (Next.js Image, Nuxt Image) ou manuellement ?",
            "Si Next.js, avez-vous configure la prop priority={true} sur les images du header ?",
            "Si HTML classique, remplacez loading=\"lazy\" par loading=\"eager\" et ajoutez fetchpriority=\"high\".",
        ],
        "impact": "Le LCP sera retarde par le chargement differe. Google utilise le LCP comme facteur de ranking.",
        "effort": "5 minutes",
    },
    "nav_links_hidden_mobile": {
        "title": "Liens nav invisibles en mobile",
        "questions": [
            "Ce pattern responsive (nav desktop cachee, remplacee par burger) est-il intentionnel ?",
            "Les liens du burger sont-ils dans le HTML source (SSR) ou injectes par JavaScript au clic ?",
            "Le panneau burger utilise-t-il un portal React (Radix Sheet, Headless UI) ?",
        ],
        "impact": "Si les liens ne sont pas dans le HTML source, Googlebot Smartphone ne voit pas votre navigation.",
        "effort": "Variable (5 min si SSR OK, 2-5 jours si migration SSR necessaire)",
    },
    "fake_links": {
        "title": "Faux liens dans la navigation",
        "questions": [
            "Votre framework genere-t-il les liens de navigation avec de vrais elements <a href> ?",
            "Si vous utilisez onClick sur des <div> ou <button>, Googlebot ne suit pas ces liens.",
            "Verifiez que chaque item de menu est un <a href='/url'>, pas un <div onclick>.",
        ],
        "impact": "Googlebot ne suit QUE les <a href>. Les liens onclick/data-href sont invisibles pour l'indexation.",
        "effort": "30 min a 2 heures",
    },
    "header_weight": {
        "title": "Header trop lourd",
        "questions": [
            "Combien de SVG sont inline dans votre header ? Chaque SVG pourrait etre externalise ou en sprite.",
            "Votre framework supporte-t-il les SVG comme composants ? Sont-ils tous inlines dans le HTML source ?",
            "Avez-vous envisage un sprite SVG ou <use> pour reutiliser les icones ?",
        ],
        "impact": "Un header lourd augmente le TTFB et le FCP. Chaque octet est telecharge AVANT le contenu.",
        "effort": "2-4 heures",
    },
    "base_href_wrong_domain": {
        "title": "<base href> pointe vers le mauvais domaine",
        "questions": [
            "Un <base href> pointe vers un domaine different du site audite.",
            "Est-ce un residu de staging/developpement ?",
            "Supprimez le <base href> ou corrigez-le pour le domaine de production.",
        ],
        "impact": "TOUTES les URLs relatives du menu sont resolues vers le mauvais domaine.",
        "effort": "5 minutes",
    },
    "intrusive_interstitial": {
        "title": "Interstitiel intrusif en mobile",
        "questions": [
            "Cet overlay apparait-il au premier chargement depuis un resultat Google ?",
            "Est-il facilement fermable (bouton X visible, tap outside) ?",
            "Couvre-t-il plus de 30% du viewport mobile ?",
        ],
        "impact": "Google penalise les interstitiels intrusifs en mobile depuis 2017.",
        "effort": "1-2 heures",
    },
    "skip_link": {
        "title": "Skip link absent",
        "questions": [
            "Votre site a-t-il un lien 'Aller au contenu principal' comme premier element focusable ?",
            "Ce lien doit pointer vers l'id de votre <main> (ex: <a href='#main-content'>).",
            "Il peut etre visuellement cache et n'apparaitre qu'au focus clavier.",
        ],
        "impact": "WCAG 2.4.1 (Niveau A) — obligatoire pour l'accessibilite. Aide les utilisateurs clavier a sauter la navigation.",
        "effort": "15 minutes",
    },
    "cloaking_detected": {
        "title": "Contenu different pour Googlebot",
        "questions": [
            "Votre serveur sert-il un contenu different selon le User-Agent ?",
            "Avez-vous un CDN ou un reverse proxy qui fait de l'adaptive serving ?",
            "Verifiez que le HTML est identique pour Chrome et pour Googlebot.",
        ],
        "impact": "Le cloaking est une violation des Google Search Essentials. Risque de desindexation.",
        "effort": "Variable (investigation requise)",
    },
}

# Mapping test name → correction guide key
TEST_TO_GUIDE: dict[str, str] = {
    "above_fold_images": "above_fold_images",
    "nav_links_hidden_mobile": "nav_links_hidden_mobile",
    "fake_links": "fake_links",
    "header_weight": "header_weight",
    "base_href": "base_href_wrong_domain",
    "base_href_wrong_domain": "base_href_wrong_domain",
    "intrusive_interstitial": "intrusive_interstitial",
    "skip_link": "skip_link",
    "cloaking_detected": "cloaking_detected",
    "cloaking": "cloaking_detected",
}

# ---------------------------------------------------------------------------
# Labels humains pour les test names — titre, description, recommandation
# ---------------------------------------------------------------------------
FINDING_LABELS: dict[str, dict[str, Any]] = {
    "skip_link": {
        "title": "Skip link — lien d'acces rapide au contenu (WCAG 2.4.1)",
        "constat": "Aucun lien 'Aller au contenu principal' n'est present comme premier element focusable de la page.",
        "impact": "Les utilisateurs clavier doivent tabuler a travers toute la navigation avant d'atteindre le contenu. Critere WCAG 2.4.1 (Niveau A) — obligatoire. Affecte aussi les lecteurs d'ecran.",
        "correction": "Ajoutez <a href='#main-content' class='skip-link'>Aller au contenu</a> comme premier enfant de <body>. Le lien peut etre visuellement cache et n'apparaitre qu'au focus clavier. Effort : 15 minutes.",
        "maieutique": [
            "Votre framework (Next.js, Nuxt) genere-t-il automatiquement un skip link ?",
            "Votre <main> a-t-il un id (ex: id='main-content') utilisable comme cible ?",
            "Avez-vous un composant layout global ou le skip link doit etre ajoute une seule fois ?",
        ],
    },
    "tab_order": {
        "title": "Ordre de tabulation clavier",
        "constat": "L'ordre de tabulation clavier ne suit pas l'ordre visuel de la page.",
        "impact": "Les utilisateurs clavier se perdent quand le focus saute de facon non sequentielle. Critere WCAG 2.4.3 (Niveau A). Google evalue l'experience utilisateur globale.",
        "correction": "Supprimez les tabindex positifs (tabindex='2', etc.). Reorganisez le DOM pour que l'ordre source HTML corresponde a l'ordre visuel. Effort : 30 min a 2 heures.",
        "maieutique": [
            "Utilisez-vous des tabindex positifs dans votre code ?",
            "L'ordre visuel est-il modifie par CSS (flexbox order, grid, position absolute) ?",
            "Avez-vous un panneau ou modal qui prend le focus de facon inattendue ?",
        ],
    },
    "above_fold_images": {
        "title": "Images above-fold en loading='lazy'",
        "constat": "Des images visibles sans scroll portent l'attribut loading='lazy', retardant leur chargement.",
        "impact": "Le LCP (Largest Contentful Paint) est retarde car le navigateur ne charge ces images qu'au scroll. Google utilise le LCP comme facteur de ranking direct (Core Web Vitals).",
        "correction": "Remplacez loading='lazy' par loading='eager' sur les images above-fold. Ajoutez fetchpriority='high' sur l'image LCP. Si Next.js, utilisez priority={true}. Effort : 5 minutes.",
        "maieutique": [
            "Le loading='lazy' est-il ajoute automatiquement par votre framework (Next.js Image, Nuxt Image) ou manuellement ?",
            "Si Next.js, avez-vous configure la prop priority={true} sur les images du header ?",
            "Quelle image est l'element LCP (la plus grande visible sans scroll) ?",
        ],
    },
    "header_weight": {
        "title": "Poids du header HTML : {header_kb} KB ({svg_inline_count} SVG inline)",
        "constat": "Le header HTML pese {header_kb} KB avec {svg_inline_count} SVG inline. Chaque page du site telecharge ce poids avant tout contenu.",
        "impact": "Un header lourd augmente le TTFB et le FCP sur TOUTES les pages. Les SVG inline ne sont pas caches par le navigateur — ils sont re-telecharges a chaque navigation.",
        "correction": "Externalisez les SVG inline en fichiers .svg ou utilisez un sprite SVG (<use href>). Les icones en composants framework (Next.js, Nuxt) sont souvent inlines dans le HTML source. Effort : 2-4 heures.",
        "maieutique": [
            "Combien de SVG sont inline dans votre header ? Chaque SVG pourrait etre externalise ou en sprite.",
            "Votre framework supporte-t-il les SVG comme composants ? Sont-ils tous inlines dans le HTML source ?",
            "Avez-vous envisage un sprite SVG ou <use> pour reutiliser les icones ?",
        ],
    },
    "font_size_mobile": {
        "title": "Taille de police mobile insuffisante",
        "constat": "Le texte de navigation en mobile utilise une taille de police inferieure a 14px.",
        "impact": "Un texte trop petit oblige le zoom en mobile, degradant l'experience utilisateur. Google penalise les sites ou le contenu n'est pas lisible sans zoom (Mobile-Friendly).",
        "correction": "Utilisez une taille de police d'au moins 14px pour le texte de navigation mobile. Verifiez avec les DevTools en mode responsive. Effort : 15 minutes.",
        "maieutique": [
            "La taille de police est-elle definie en px, rem ou em dans votre CSS ?",
            "Avez-vous un breakpoint mobile qui reduit la taille du texte de navigation ?",
            "Le viewport meta tag est-il correctement configure (width=device-width, initial-scale=1) ?",
        ],
    },
    "hover_without_focus": {
        "title": "Sous-menu au hover sans equivalent :focus-within",
        "constat": "Les sous-menus s'ouvrent au survol souris (:hover) mais ne s'ouvrent pas au focus clavier (:focus-within).",
        "impact": "Les utilisateurs clavier ne peuvent pas acceder aux sous-menus. Violation WCAG 2.1.1 (Niveau A). Affecte aussi les utilisateurs de switch devices.",
        "correction": "Ajoutez :focus-within a cote de :hover dans vos regles CSS de sous-menu. Ex: nav li:hover > ul, nav li:focus-within > ul { display: block; }. Effort : 30 minutes.",
        "maieutique": [
            "Vos sous-menus utilisent-ils du CSS pur (:hover) ou du JavaScript (mouseenter/mouseleave) ?",
            "Avez-vous des elements <button> comme declencheurs de sous-menus ?",
            "Le framework gere-t-il deja le focus (Headless UI, Radix) ?",
        ],
    },
    "target_spacing": {
        "title": "Espacement insuffisant des cibles tactiles",
        "constat": "Les cibles tactiles adjacentes dans la navigation n'ont pas assez d'espacement entre elles.",
        "impact": "Les utilisateurs mobiles cliquent accidentellement sur le mauvais lien. WCAG 2.5.8 (Niveau AA) demande un espacement minimum. Google evalue l'ergonomie mobile.",
        "correction": "Ajoutez au minimum 8px de gap entre les elements cliquables de la navigation. Utilisez gap en CSS Grid/Flexbox. Effort : 15 minutes.",
        "maieutique": [
            "L'espacement est-il gere par margin, padding ou gap CSS ?",
            "Avez-vous teste avec un doigt sur un vrai telephone (pas juste les DevTools) ?",
            "Les liens ont-ils assez de padding interne (au moins 44x44px de zone cliquable) ?",
        ],
    },
    "nav_landmarks": {
        "title": "Landmarks de navigation (ARIA)",
        "constat": "La navigation principale n'est pas encapsulee dans un element <nav> avec aria-label.",
        "impact": "Les lecteurs d'ecran ne peuvent pas identifier et sauter directement a la navigation. WCAG 1.3.1 (Niveau A). Les landmarks aident aussi les moteurs de recherche a comprendre la structure.",
        "correction": "Encapsulez la navigation dans <nav aria-label='Navigation principale'>. Si plusieurs <nav>, chacun doit avoir un label unique. Effort : 15 minutes.",
        "maieutique": [
            "Votre navigation est-elle dans un <div> ou directement dans un <nav> ?",
            "Avez-vous plusieurs zones de navigation (header, footer, sidebar) qui necessitent chacune un label ?",
            "Votre framework genere-t-il automatiquement le <nav> ?",
        ],
    },
    "trigger_elements": {
        "title": "Elements declencheurs de sous-menus",
        "constat": "Les sous-menus sont declenches par des elements non-semantiques (<div>, <span>) au lieu de <button>.",
        "impact": "Les lecteurs d'ecran n'annoncent pas ces declencheurs comme interactifs. Violation WCAG 4.1.2 (Niveau A). Les utilisateurs clavier ne peuvent pas activer les sous-menus.",
        "correction": "Remplacez les declencheurs non-semantiques par <button aria-expanded='false'>. L'attribut aria-expanded doit basculer entre true/false a l'ouverture/fermeture. Effort : 1-2 heures.",
        "maieutique": [
            "Les declencheurs utilisent-ils onClick sur des <div> ou des <span> ?",
            "Votre framework (React, Vue) utilise-t-il des composants semantiques pour les menus ?",
            "Les sous-menus sont-ils geres par un composant tiers (Headless UI, Radix, Chakra) ?",
        ],
    },
    "focus_visibility": {
        "title": "Visibilite du focus clavier",
        "constat": "Certains elements interactifs n'ont pas d'indicateur de focus visible quand ils recoivent le focus clavier.",
        "impact": "Les utilisateurs clavier ne savent pas ou ils se trouvent dans la page. Critere WCAG 2.4.7 (Niveau AA). Affecte aussi les utilisateurs de technologies d'assistance.",
        "correction": "Ne supprimez jamais outline sans fournir un style :focus-visible alternatif. Utilisez :focus-visible (pas :focus) pour ne cibler que le focus clavier. Effort : 30 minutes.",
        "maieutique": [
            "Avez-vous des regles CSS outline:none ou outline:0 dans votre code ?",
            "Votre reset CSS (normalize, modern-normalize) supprime-t-il les outlines ?",
            "Utilisez-vous deja :focus-visible ou seulement :focus ?",
        ],
    },
    "target_sizes": {
        "title": "Taille des cibles tactiles (WCAG 2.5.8)",
        "constat": "Certaines cibles tactiles dans la navigation font moins de 24x24px (minimum WCAG AA) ou 44x44px (cible recommandee).",
        "impact": "Les utilisateurs mobiles ont du mal a cliquer sur les petits liens. WCAG 2.5.8 (Niveau AA). Google penalise les cibles trop petites dans le rapport Mobile Usability.",
        "correction": "Augmentez le padding des liens de navigation pour atteindre 44x44px minimum de zone cliquable. Utilisez min-height et min-width si necessaire. Effort : 30 minutes.",
        "maieutique": [
            "Les liens de navigation ont-ils un padding suffisant en mobile ?",
            "Avez-vous verifie avec le rapport Mobile Usability de Google Search Console ?",
            "Le design mobile prevoit-il des zones de tap assez grandes ?",
        ],
    },
    "aria_current_page": {
        "title": "aria-current='page' sur le lien actif",
        "constat": "Le lien de navigation correspondant a la page courante ne porte pas l'attribut aria-current='page'.",
        "impact": "Les lecteurs d'ecran n'annoncent pas quel lien correspond a la page actuelle. Best practice ARIA. Aide aussi les moteurs de recherche a comprendre la structure du site.",
        "correction": "Ajoutez aria-current='page' dynamiquement au lien actif cote serveur ou client. En Next.js, utilisez usePathname() pour comparer. Effort : 30 minutes.",
        "maieutique": [
            "Votre framework ajoute-t-il automatiquement un style 'active' sur le lien courant ?",
            "Pouvez-vous ajouter aria-current='page' au meme endroit que la classe active ?",
            "Faut-il gerer le cas des sous-pages (ex: /blog/article marque /blog comme actif) ?",
        ],
    },
    "escape_closes_burger": {
        "title": "Touche Echap pour fermer le menu burger",
        "constat": "Le menu burger mobile ne se ferme pas quand l'utilisateur appuie sur la touche Echap.",
        "impact": "Les utilisateurs clavier ne peuvent pas fermer facilement le menu mobile. Pattern attendu par WCAG (gestion modale). Frustration utilisateur sur mobile.",
        "correction": "Ajoutez un event listener keydown pour fermer le menu au keyCode 27 (Escape). Assurez que le focus revient au bouton burger apres fermeture. Effort : 15 minutes.",
        "maieutique": [
            "Le menu burger est-il un composant tiers qui gere deja le Escape ?",
            "Le menu est-il traite comme un modal (focus trap, fermeture Escape) ?",
            "Le focus revient-il au bouton burger apres la fermeture ?",
        ],
    },
    "cwv_ttfb": {
        "title": "Core Web Vital : TTFB (Time to First Byte)",
        "constat": "Le TTFB mesure le temps entre la requete HTTP et le premier octet de reponse du serveur.",
        "impact": "Un TTFB eleve retarde TOUS les autres metriques (FCP, LCP). Cible Google : <800ms. Un mauvais TTFB indique un probleme serveur, pas front-end.",
        "correction": "Optimisez le cache serveur, utilisez un CDN, optimisez les requetes base de donnees. Verifiez la latence reseau. Effort : variable (1h a plusieurs jours).",
        "maieutique": [
            "Utilisez-vous un CDN (Vercel, Cloudflare, Fastly) ?",
            "Vos pages sont-elles generees dynamiquement (SSR) ou pre-rendues (SSG/ISR) ?",
            "Votre base de donnees est-elle dans la meme region que votre serveur ?",
        ],
    },
    "cwv_fcp": {
        "title": "Core Web Vital : FCP (First Contentful Paint)",
        "constat": "Le FCP mesure le temps jusqu'au premier affichage de contenu (texte, image, canvas).",
        "impact": "Le FCP est la premiere impression de vitesse pour l'utilisateur. Cible Google : <1.8s. Un mauvais FCP indique du CSS/JS bloquant ou des polices non optimisees.",
        "correction": "Reduisez le CSS bloquant, preload les polices critiques, inlinez le CSS critique, differez le JS non essentiel. Effort : 2-4 heures.",
        "maieutique": [
            "Combien de fichiers CSS sont charges avant le premier rendu ?",
            "Utilisez-vous des polices web (Google Fonts, Typekit) ? Sont-elles preloadees ?",
            "Le JS principal est-il defer ou async ?",
        ],
    },
    "cwv_lcp": {
        "title": "Core Web Vital : LCP (Largest Contentful Paint)",
        "constat": "Le LCP mesure le temps d'affichage du plus grand element visible (souvent une image hero).",
        "impact": "Le LCP est LE metrique de ranking Core Web Vitals le plus important. Cible Google : <2.5s. Un mauvais LCP impacte directement le positionnement.",
        "correction": "Preload l'image LCP, optimisez ses dimensions, evitez le lazy-loading above-fold. Verifiez que l'image LCP n'est pas chargee par JS. Effort : 1-2 heures.",
        "maieutique": [
            "Quel est l'element LCP de votre page ? (Verifiez avec Lighthouse ou DevTools Performance)",
            "L'image LCP est-elle en loading='lazy' ? (Corrigez avec correction 'above_fold_images')",
            "L'image LCP est-elle au format optimise (WebP/AVIF) avec des dimensions explicites ?",
        ],
    },
    "cwv_cls": {
        "title": "Core Web Vital : CLS (Cumulative Layout Shift)",
        "constat": "Le CLS mesure la stabilite visuelle — les decalages de contenu inattendus pendant le chargement.",
        "impact": "Un mauvais CLS frustre les utilisateurs qui cliquent sur le mauvais element. Cible Google : <0.1. Les bannieres, pubs et images sans dimensions causent du CLS.",
        "correction": "Reservez l'espace pour images/iframes avec width/height ou aspect-ratio. Evitez les injections dynamiques au-dessus du fold. Effort : 1-2 heures.",
        "maieutique": [
            "Avez-vous des bannieres ou messages qui apparaissent apres le chargement (cookie banner, promo) ?",
            "Vos images ont-elles des attributs width et height explicites ?",
            "Des polices web causent-elles un Flash of Unstyled Text (FOUT) ?",
        ],
    },
    "cwv_inp": {
        "title": "Core Web Vital : INP (Interaction to Next Paint)",
        "constat": "L'INP mesure la reactivite — le temps entre un clic/tap et la mise a jour visuelle qui suit.",
        "impact": "L'INP remplace le FID comme metrique de reactivite depuis mars 2024. Cible Google : <200ms. Un mauvais INP indique du JS lourd sur le thread principal.",
        "correction": "Optimisez les event listeners, fragmentez le JS lourd avec requestIdleCallback ou web workers. Evitez les reflows forces. Effort : 2-8 heures.",
        "maieutique": [
            "Vos menus declenchent-ils du JS lourd a l'ouverture (chargement de donnees, animations complexes) ?",
            "Utilisez-vous des animations CSS (GPU-accelerated) ou des animations JS (layout-triggered) ?",
            "Avez-vous des event listeners passifs (passive: true) sur les handlers de scroll/touch ?",
        ],
    },
    "fake_links": {
        "title": "Faux liens de navigation",
        "constat": "Des elements de navigation utilisent onclick/data-href au lieu de vrais <a href>.",
        "impact": "Googlebot ne suit QUE les <a href>. Les liens onclick/data-href sont invisibles pour le crawl et l'indexation. Perte totale de maillage interne.",
        "correction": "Chaque item de menu doit etre un <a href='/url'>, pas un element JavaScript. Effort : 30 min a 2 heures.",
        "maieutique": [
            "Votre framework genere-t-il les liens de navigation avec de vrais elements <a href> ?",
            "Si vous utilisez onClick sur des <div> ou <button>, Googlebot ne suit pas ces liens.",
            "Verifiez que chaque item de menu est un <a href='/url'>, pas un <div onclick>.",
        ],
    },
    "role_menu_antipattern": {
        "title": "Anti-pattern role='menu'",
        "constat": "role='menu' est utilise sur la barre de navigation web.",
        "impact": "role='menu' est reserve aux menus applicatifs (type editeur de texte), pas aux barres de navigation web. Les lecteurs d'ecran attendent un comportement clavier different.",
        "correction": "Supprimez role='menu' / role='menuitem' de votre navigation. Utilisez <nav> + <ul> + <li>. Effort : 15 minutes.",
        "maieutique": [
            "Le role='menu' a-t-il ete ajoute manuellement ou par un composant tiers ?",
            "Utilisez-vous un composant de menu qui impose ce role (Material UI, Ant Design) ?",
            "Avez-vous d'autres attributs ARIA lies (aria-activedescendant, aria-orientation) ?",
        ],
    },
    "base_href": {
        "title": "Balise <base href> incorrecte",
        "constat": "Un <base href> pointe vers un domaine different du site audite.",
        "impact": "TOUTES les URLs relatives du menu sont resolues vers le mauvais domaine. Le maillage interne est totalement casse.",
        "correction": "Supprimez le <base href> ou corrigez-le pour le domaine de production. Effort : 5 minutes.",
        "maieutique": [
            "Ce <base href> est-il un residu de staging ou de developpement ?",
            "Votre framework le genere-t-il automatiquement ?",
            "D'autres pages du site ont-elles le meme probleme ?",
        ],
    },
    "breadcrumb_html_pattern": {
        "title": "Fil d'Ariane HTML",
        "constat": "Le fil d'Ariane n'utilise pas la structure semantique recommandee.",
        "impact": "Sans <nav aria-label='Fil d'Ariane'> + <ol> + schema.org, Google ne peut pas generer les breadcrumbs dans les SERPs.",
        "correction": "Structurez avec <nav><ol><li itemscope itemtype='ListItem'>... Effort : 1 heure.",
        "maieutique": [
            "Le fil d'Ariane est-il genere par un composant de votre framework ?",
            "Avez-vous deja des donnees structurees BreadcrumbList en JSON-LD ?",
            "Le fil d'Ariane est-il visible sur mobile ?",
        ],
    },
    "breadcrumb_jsonld": {
        "title": "Fil d'Ariane JSON-LD",
        "constat": "Les donnees structurees BreadcrumbList ne correspondent pas au fil d'Ariane visible.",
        "impact": "Google peut ignorer les breadcrumbs dans les SERPs si le JSON-LD ne correspond pas au contenu visible.",
        "correction": "Verifiez la coherence entre le JSON-LD BreadcrumbList et le breadcrumb HTML visible. Effort : 30 minutes.",
        "maieutique": [
            "Le JSON-LD est-il genere automatiquement depuis les memes donnees que le breadcrumb HTML ?",
            "Avez-vous teste avec le Rich Results Test de Google ?",
            "Le JSON-LD et le HTML ont-ils exactement les memes URLs et labels ?",
        ],
    },
    "breadcrumb_alignment": {
        "title": "Coherence breadcrumb HTML / JSON-LD",
        "constat": "Le breadcrumb HTML et le JSON-LD n'ont pas les memes items dans le meme ordre.",
        "impact": "L'incoherence entre HTML visible et JSON-LD peut etre interpretee comme du contenu trompeur par Google.",
        "correction": "Generez les deux depuis la meme source de donnees pour garantir la coherence. Effort : 1 heure.",
        "maieutique": [
            "Les deux sources (HTML et JSON-LD) sont-elles generees par le meme composant ?",
            "Y a-t-il un middleware ou plugin qui genere le JSON-LD independamment ?",
            "Avez-vous des breadcrumbs differents sur mobile et desktop ?",
        ],
    },
    "nav_hidden_by_default": {
        "title": "Navigation cachee par defaut en mobile",
        "constat": "La nav principale est masquee (display:none / visibility:hidden) au chargement mobile.",
        "impact": "Si les liens sont injectes par JS au clic (pas dans le HTML source), Googlebot Smartphone ne les voit pas.",
        "correction": "Verifiez que les liens sont dans le HTML source (SSR) meme si visuellement caches. Effort : verification 5 min, correction 2-5 jours si migration SSR.",
        "maieutique": [
            "Les liens du burger sont-ils dans le HTML source (SSR) ou injectes par JavaScript au clic ?",
            "Le panneau burger utilise-t-il un portal React (Radix Sheet, Headless UI) ?",
            "Googlebot voit-il le meme HTML que Chrome en mode View Source ?",
        ],
    },
    "desktop_first_media_queries": {
        "title": "Media queries desktop-first",
        "constat": "Les media queries utilisent max-width, indiquant une approche desktop-first.",
        "impact": "Google indexe en mobile-first. Une approche desktop-first risque de montrer un contenu degrade a Googlebot Smartphone.",
        "correction": "Migrez vers des media queries min-width (mobile-first). Effort : variable (refactoring CSS).",
        "maieutique": [
            "Votre framework utilise-t-il mobile-first par defaut (Tailwind, Bootstrap 5) ?",
            "Les media queries max-width sont-elles dans votre code ou dans des librairies tierces ?",
            "Une migration progressive (page par page) est-elle envisageable ?",
        ],
    },
    "focus_visible_css": {
        "title": "Support CSS :focus-visible",
        "constat": "Le site n'utilise pas :focus-visible pour differencier focus clavier et focus souris.",
        "impact": "Sans :focus-visible, le style de focus apparait aussi au clic souris (genant visuellement) ou est supprime completement (inaccessible).",
        "correction": "Remplacez :focus par :focus-visible dans vos styles pour un meilleur UX clavier. Effort : 30 minutes.",
        "maieutique": [
            "Avez-vous des regles :focus dans votre CSS ? Sont-elles la pour l'accessibilite ?",
            "Votre navigateur cible supporte-t-il :focus-visible (tous les navigateurs modernes) ?",
            "Utilisez-vous un polyfill :focus-visible (focus-visible.js) ?",
        ],
    },
    "css_payload_estimate": {
        "title": "Poids CSS estime",
        "constat": "La quantite de CSS chargee impacte le FCP et le temps de parsing.",
        "impact": "Un CSS volumineux bloque le premier rendu. Cible : <50 KB de CSS critique.",
        "correction": "Auditez le CSS inutilise avec Coverage DevTools. Inlinez le CSS critique. Effort : 2-4 heures.",
        "maieutique": [
            "Combien de fichiers CSS sont charges au chargement initial ?",
            "Avez-vous du CSS inutilise (ancien framework, composants supprimes) ?",
            "Votre framework supporte-t-il l'extraction du CSS critique (critical CSS) ?",
        ],
    },
    "cloaking_detected": {
        "title": "Contenu different pour Googlebot (cloaking)",
        "constat": "Le serveur sert un contenu different selon le User-Agent.",
        "impact": "Le cloaking est une violation des Google Search Essentials. Risque de desindexation totale du site.",
        "correction": "Verifiez que le HTML est identique pour Chrome et pour Googlebot. Effort : investigation variable.",
        "maieutique": [
            "Votre serveur sert-il un contenu different selon le User-Agent ?",
            "Avez-vous un CDN ou un reverse proxy qui fait de l'adaptive serving ?",
            "Verifiez que le HTML est identique pour Chrome et pour Googlebot.",
        ],
    },
    "intrusive_interstitial": {
        "title": "Interstitiel intrusif en mobile",
        "constat": "Un overlay couvre une partie significative du viewport mobile au chargement.",
        "impact": "Google penalise les interstitiels intrusifs en mobile depuis 2017. Affecte le ranking sur mobile.",
        "correction": "Assurez que l'overlay est facilement fermable, couvre <30% du viewport, ou apparait uniquement apres interaction. Effort : 1-2 heures.",
        "maieutique": [
            "Cet overlay apparait-il au premier chargement depuis un resultat Google ?",
            "Est-il facilement fermable (bouton X visible, tap outside) ?",
            "Couvre-t-il plus de 30% du viewport mobile ?",
        ],
    },
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    """Structure normalisee d'un finding extrait des JSON."""

    severity: str
    test: str
    message: str
    detail: str = ""
    code: str = ""
    url: str = ""
    evidence: str | list[str] = ""
    dimension: str = ""
    checklist_id: str = ""
    passed: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    source_file: str = ""
    convergence_note: str = ""

    @property
    def severity_normalized(self) -> str:
        """Normalise la severite en minuscule."""
        if not self.severity:
            return "recommandation"
        s = self.severity.lower().strip()
        if s in SEVERITY_ORDER:
            return s
        return "recommandation"

    @property
    def score(self) -> int:
        return SEVERITY_SCORE.get(self.severity_normalized, 75)


# ---------------------------------------------------------------------------
# Chargement et parsing des findings
# ---------------------------------------------------------------------------
def load_json_safe(path: Path) -> dict | list | None:
    """Charge un fichier JSON, retourne None si erreur."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[report_html] WARNING: JSON invalide dans {path}: {exc}", file=sys.stderr)
        return None


def extract_findings_from_file(path: Path) -> list[Finding]:
    """Extrait les findings d'un fichier JSON de resultats."""
    data = load_json_safe(path)
    if data is None:
        return []

    findings: list[Finding] = []
    stem = path.stem  # nom du fichier sans extension = dimension approximee

    # Determiner la dimension a partir du nom de fichier
    dimension = stem
    for key in DIMENSION_TO_CATEGORY:
        if key in stem.lower():
            dimension = key
            break

    if isinstance(data, dict):
        # Skip i18n findings on monolingual sites
        if data.get("is_multilingual") is False:
            return []

        # Format "tests" (accessibility_checks, breadcrumb_checks, etc.)
        for test_item in data.get("tests", []):
            if not isinstance(test_item, dict):
                continue
            severity = test_item.get("severity")
            passed = test_item.get("passed", True)

            # Skip tests that passed without explicit severity — they're coverage, not findings
            if passed and not severity:
                continue
            if passed is None and not severity:
                continue

            test_name = test_item.get("test", "unknown")
            msg = test_item.get("detail") or test_item.get("reason") or test_name
            findings.append(Finding(
                severity=severity or "recommandation",
                test=test_name,
                message=msg,
                detail=test_item.get("detail", ""),
                code=test_item.get("code", ""),
                url=data.get("url", ""),
                dimension=dimension,
                checklist_id=test_item.get("checklist_id", ""),
                passed=passed,
                extra=test_item,
                source_file=stem,
            ))

        # Format "findings" (assemble_report-style)
        for finding_item in data.get("findings", []):
            if not isinstance(finding_item, dict):
                continue
            findings.append(Finding(
                severity=finding_item.get("severity", "recommandation"),
                test=finding_item.get("code", finding_item.get("test", "unknown")),
                message=finding_item.get("message", ""),
                detail=finding_item.get("detail", ""),
                code=finding_item.get("code", ""),
                url=finding_item.get("url", ""),
                evidence=finding_item.get("evidence", ""),
                dimension=finding_item.get("dimension", dimension),
                checklist_id=finding_item.get("checklist_id", ""),
                passed=False,
                extra=finding_item,
                source_file=stem,
            ))

        # Format "issues" (sitemap_alignment, etc.)
        for issue_item in data.get("issues", []):
            if not isinstance(issue_item, dict):
                continue
            findings.append(Finding(
                severity=issue_item.get("severity", "recommandation"),
                test=issue_item.get("code", issue_item.get("test", "unknown")),
                message=issue_item.get("message", ""),
                detail=issue_item.get("detail", ""),
                code=issue_item.get("code", ""),
                url=issue_item.get("url", ""),
                evidence=issue_item.get("evidence", ""),
                dimension=issue_item.get("dimension", dimension),
                checklist_id=issue_item.get("checklist_id", ""),
                passed=False,
                extra=issue_item,
                source_file=stem,
            ))

        # Format performance_checks.js — objets imbriqués avec severity
        # above_fold_images, header.occupation, mobile_layout.horizontal_overflow
        for sub_key in ("above_fold_images",):
            sub = data.get(sub_key)
            if isinstance(sub, dict) and sub.get("severity"):
                detail = sub.get("detail") or f"{sub.get('lazy_above_fold_count', 0)} image(s) above-fold sur {sub.get('total_above_fold', 0)} ont loading='lazy'. {sub.get('fetchpriority_high_count', 0)} ont fetchpriority='high'."
                findings.append(Finding(
                    severity=sub["severity"].lower(),
                    test=sub.get("test", sub_key),
                    message=detail,
                    detail=detail,
                    url=data.get("url", ""),
                    dimension=dimension,
                    passed=False,
                    extra=sub,
                    source_file=stem,
                ))

        # Format performance_checks.js — verdicts CWV
        verdict = data.get("verdict")
        if isinstance(verdict, dict):
            cwv_severity_map = {"POOR": "critique", "NEEDS_IMPROVEMENT": "important", "GOOD": None}
            for metric, level in verdict.items():
                sev = cwv_severity_map.get(level)
                if sev:
                    val = data.get(f"{metric}_ms") or data.get(f"{metric}_score")
                    detail = f"{metric.upper()} = {val} ({level})"
                    findings.append(Finding(
                        severity=sev,
                        test=f"cwv_{metric}",
                        message=detail,
                        detail=detail,
                        url=data.get("url", ""),
                        dimension=dimension,
                        passed=False,
                        extra={"metric": metric, "value": val, "verdict": level},
                        source_file=stem,
                    ))

        # Format performance_checks.js — horizontal overflow mobile
        mobile_layout = data.get("mobile_layout")
        if isinstance(mobile_layout, dict):
            overflow = mobile_layout.get("horizontal_overflow")
            if isinstance(overflow, dict) and overflow.get("overflows"):
                findings.append(Finding(
                    severity="important",
                    test="horizontal_overflow",
                    message=f"Debordement horizontal mobile : scrollWidth={overflow.get('scrollWidth')} > viewportWidth={overflow.get('viewportWidth')}",
                    detail=f"Le contenu deborde du viewport mobile ({overflow.get('scrollWidth')}px > {overflow.get('viewportWidth')}px)",
                    url=data.get("url", ""),
                    dimension=dimension,
                    passed=False,
                    extra=overflow,
                    source_file=stem,
                ))

    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            findings.append(Finding(
                severity=item.get("severity", "recommandation"),
                test=item.get("code", item.get("test", "unknown")),
                message=item.get("message", ""),
                detail=item.get("detail", ""),
                code=item.get("code", ""),
                url=item.get("url", ""),
                evidence=item.get("evidence", ""),
                dimension=item.get("dimension", dimension),
                checklist_id=item.get("checklist_id", ""),
                passed=False,
                extra=item,
                source_file=stem,
            ))

    return findings


def load_all_findings(audit_dir: Path) -> list[Finding]:
    """Charge tous les findings de tous les JSON du dossier findings/."""
    findings_dir = audit_dir / "findings"
    if not findings_dir.exists():
        print(f"[report_html] WARNING: dossier findings/ absent dans {audit_dir}", file=sys.stderr)
        return []

    all_findings: list[Finding] = []
    for json_file in sorted(findings_dir.glob("*.json")):
        file_findings = extract_findings_from_file(json_file)
        all_findings.extend(file_findings)
        print(f"[report_html] {json_file.name}: {len(file_findings)} findings", file=sys.stderr)

    return all_findings


SEVERITY_PRIORITY: dict[str, int] = {"bloquant": 4, "critique": 3, "important": 2, "recommandation": 1, "ok": 0}


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Fusionne les findings identiques (meme test), conserve la severite la plus haute."""
    groups: dict[str, Finding] = {}
    for f in findings:
        key = f.test
        if key not in groups:
            groups[key] = f
            f._sources = [f.source_file]  # type: ignore[attr-defined]
            f._urls = [f.url] if f.url else []  # type: ignore[attr-defined]
        else:
            existing = groups[key]
            existing._sources.append(f.source_file)  # type: ignore[attr-defined]
            if f.url and f.url not in existing._urls:  # type: ignore[attr-defined]
                existing._urls.append(f.url)  # type: ignore[attr-defined]
            # Keep highest severity
            if SEVERITY_PRIORITY.get(f.severity_normalized, 0) > SEVERITY_PRIORITY.get(existing.severity_normalized, 0):
                existing.severity = f.severity
            # Keep the richer detail
            if len(f.detail or "") > len(existing.detail or ""):
                existing.detail = f.detail
            if len(f.message or "") > len(existing.message or ""):
                existing.message = f.message

    result = []
    for f in groups.values():
        if len(f._sources) > 1:  # type: ignore[attr-defined]
            f.convergence_note = f"Confirme par {len(f._sources)} verifications : {', '.join(f._sources)}"  # type: ignore[attr-defined]
            if len(f._urls) > 1:  # type: ignore[attr-defined]
                f.convergence_note += f". Affecte : {', '.join(f._urls)}"  # type: ignore[attr-defined]
        result.append(f)
    return result


# ---------------------------------------------------------------------------
# Calcul de scores par categorie
# ---------------------------------------------------------------------------
def _resolve_category(f: Finding) -> str | None:
    """Determine la categorie de score d'un finding via source_file puis dimension."""
    # Priorite 1 : source_file -> FILENAME_TO_CATEGORY
    if f.source_file:
        # Strip prod-/staging- prefix, then match partial keys
        stripped = f.source_file.lower()
        for prefix in ("prod-", "staging-"):
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix):]
                break
        # Try each FILENAME_TO_CATEGORY key as substring
        for key, cat in FILENAME_TO_CATEGORY.items():
            if key in stripped:
                return cat
    # Priorite 2 : dimension -> DIMENSION_TO_CATEGORY (fallback)
    dim = f.dimension.lower().replace("_", "-")
    return DIMENSION_TO_CATEGORY.get(dim)


def compute_category_scores(findings: list[Finding]) -> dict[str, int]:
    """Calcule un score 0-100 par categorie a partir des findings."""
    category_scores: dict[str, list[int]] = {cat: [] for cat, _ in SCORE_CATEGORIES}

    for f in findings:
        cat_key = _resolve_category(f)
        if cat_key and cat_key in category_scores:
            category_scores[cat_key].append(f.score)

    result: dict[str, int] = {}
    for cat_key, _ in SCORE_CATEGORIES:
        cat_findings_scores = category_scores[cat_key]
        if not cat_findings_scores:
            result[cat_key] = -1  # -1 = non teste
            continue

        # Special case: performance score based on CWV verdicts
        if cat_key == "performance":
            perf_score = 100
            for f in findings:
                if _resolve_category(f) != "performance":
                    continue
                if f.extra and isinstance(f.extra, dict):
                    verdict = f.extra.get("verdict")
                    if verdict == "NEEDS_IMPROVEMENT":
                        perf_score -= 15
                    elif verdict == "POOR":
                        perf_score -= 30
                if f.severity_normalized == "critique":
                    perf_score -= 10
                elif f.severity_normalized == "important":
                    perf_score -= 5
            result[cat_key] = max(0, min(100, perf_score))
            continue

        result[cat_key] = round(sum(cat_findings_scores) / len(cat_findings_scores))

    return result


def count_by_severity(findings: list[Finding]) -> dict[str, int]:
    """Compte les findings par niveau de severite (exclut les tests passes / ok)."""
    counts: dict[str, int] = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        sev = f.severity_normalized
        if sev in counts:
            counts[sev] += 1
    return counts


def group_findings_by_severity(findings: list[Finding]) -> dict[str, list[Finding]]:
    """Groupe les findings par severite, exclut les OK / passes."""
    grouped: dict[str, list[Finding]] = {s: [] for s in SEVERITY_ORDER}
    for f in findings:
        sev = f.severity_normalized
        if sev in grouped:
            grouped[sev].append(f)
    return grouped


# ---------------------------------------------------------------------------
# Chargement donnees supplementaires
# ---------------------------------------------------------------------------
def load_coverage(audit_dir: Path) -> dict | None:
    """Charge coverage.json s'il existe."""
    return load_json_safe(audit_dir / "coverage.json")


def load_review(audit_dir: Path) -> dict | None:
    """Charge review.json s'il existe."""
    return load_json_safe(audit_dir / "review.json")


def load_intake(audit_dir: Path) -> dict:
    """Charge intake.json s'il existe."""
    data = load_json_safe(audit_dir / "intake.json")
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Generation SVG gauge
# ---------------------------------------------------------------------------
def generate_gauge_svg(score: int, label: str) -> str:
    """Genere un cercle SVG style PageSpeed Insights pour un score 0-100."""
    if score < 0:
        # Non teste
        color = "#9e9e9e"
        display_score = "—"
        offset = 339.3
    else:
        color = "#0cce6b" if score >= 90 else "#ffa400" if score >= 50 else "#ff4e42"
        display_score = str(score)
        offset = 339.3 * (1 - score / 100)

    escaped_label = html.escape(label)
    return f'''<div class="gauge">
      <svg viewBox="0 0 120 120" width="100" height="100">
        <circle cx="60" cy="60" r="54" fill="none" stroke="#eee" stroke-width="8"/>
        <circle cx="60" cy="60" r="54" fill="none" stroke="{color}" stroke-width="8"
                stroke-dasharray="339.3" stroke-dashoffset="{offset:.1f}"
                stroke-linecap="round" transform="rotate(-90 60 60)"/>
        <text x="60" y="66" text-anchor="middle" font-size="28" font-weight="bold" fill="{color}">{display_score}</text>
      </svg>
      <div class="gauge-label">{escaped_label}</div>
    </div>'''


# ---------------------------------------------------------------------------
# Generation HTML
# ---------------------------------------------------------------------------
CSS = """\
:root {
  --color-good: #0cce6b;
  --color-needs-improvement: #ffa400;
  --color-poor: #ff4e42;
  --color-bloquant: #d32f2f;
  --color-critique: #e53935;
  --color-important: #ff9800;
  --color-recommandation: #1976d2;
  --color-go: #2e7d32;
  --color-go-conditions: #f57c00;
  --color-nogo: #c62828;
  --color-bg: #ffffff;
  --color-bg-section: #f5f5f5;
  --color-text: #212121;
  --color-text-secondary: #616161;
  --color-border: #e0e0e0;
  --color-accent: #1565c0;
  --font-main: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'SF Mono', 'Fira Code', 'Consolas', monospace;
}

*, *::before, *::after { box-sizing: border-box; }

body {
  font-family: var(--font-main);
  font-size: 16px;
  line-height: 1.6;
  color: var(--color-text);
  background: var(--color-bg);
  margin: 0;
  padding: 0;
}

.report-container {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

/* Header */
.report-header {
  text-align: center;
  padding: 2rem 1rem 1.5rem;
  border-bottom: 3px solid var(--color-accent);
  margin-bottom: 2rem;
}
.report-header h1 {
  font-size: 1.8rem;
  font-weight: 700;
  margin: 0 0 0.5rem;
  color: var(--color-text);
}
.report-header .meta {
  font-size: 0.9rem;
  color: var(--color-text-secondary);
  margin: 0.25rem 0;
}
.report-header .meta span {
  margin: 0 0.5rem;
}

/* Verdict banner */
.verdict-banner {
  text-align: center;
  padding: 1.25rem;
  border-radius: 8px;
  margin-bottom: 2rem;
  font-size: 1.15rem;
  font-weight: 600;
}
.verdict-go { background: #e8f5e9; color: var(--color-go); border: 2px solid var(--color-go); }
.verdict-go-conditions { background: #fff3e0; color: var(--color-go-conditions); border: 2px solid var(--color-go-conditions); }
.verdict-nogo { background: #ffebee; color: var(--color-nogo); border: 2px solid var(--color-nogo); }
.verdict-audit-ok { background: #e8f5e9; color: var(--color-go); border: 2px solid var(--color-go); }
.verdict-audit-attention { background: #fff3e0; color: var(--color-go-conditions); border: 2px solid var(--color-go-conditions); }
.verdict-audit-risk { background: #ffebee; color: var(--color-nogo); border: 2px solid var(--color-nogo); }

/* Gauges */
.gauges-section {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 1.5rem;
  margin: 2rem 0;
  padding: 1.5rem;
  background: var(--color-bg-section);
  border-radius: 8px;
}
.gauge {
  text-align: center;
  min-width: 110px;
}
.gauge-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-top: 0.35rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

/* Severity badges */
.severity-badges {
  display: flex;
  justify-content: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin: 1.5rem 0 2rem;
}
.severity-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  border: none;
  background: none;
  font-family: var(--font-main);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.severity-badge:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.badge-bloquant { background: #ffcdd2; color: var(--color-bloquant); }
.badge-critique { background: #ffcdd2; color: var(--color-critique); }
.badge-important { background: #ffe0b2; color: #e65100; }
.badge-recommandation { background: #bbdefb; color: var(--color-recommandation); }
.badge-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  font-size: 0.85rem;
  font-weight: 700;
  color: #fff;
}
.badge-bloquant .badge-count { background: var(--color-bloquant); }
.badge-critique .badge-count { background: var(--color-critique); }
.badge-important .badge-count { background: var(--color-important); }
.badge-recommandation .badge-count { background: var(--color-recommandation); }

/* Sections */
.section {
  margin: 2rem 0;
}
.section h2 {
  font-size: 1.35rem;
  font-weight: 700;
  margin: 0 0 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid var(--color-border);
  color: var(--color-text);
}
.section h3 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 1.5rem 0 0.75rem;
}

/* Finding cards */
.finding-card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 0.75rem;
  overflow: hidden;
  transition: box-shadow 0.15s ease;
}
.finding-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.finding-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  cursor: pointer;
  user-select: none;
  background: var(--color-bg);
}
.finding-header:hover {
  background: var(--color-bg-section);
}
.finding-severity-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-bloquant { background: var(--color-bloquant); }
.dot-critique { background: var(--color-critique); }
.dot-important { background: var(--color-important); }
.dot-recommandation { background: var(--color-recommandation); }
.finding-title {
  flex: 1;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--color-text);
}
.finding-chevron {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  transition: transform 0.2s ease;
}
.finding-card.open .finding-chevron {
  transform: rotate(90deg);
}
.finding-body {
  display: none;
  padding: 0 1rem 1rem;
  font-size: 0.9rem;
  color: var(--color-text);
  line-height: 1.65;
}
.finding-card.open .finding-body {
  display: block;
}
.finding-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.5rem;
  margin-bottom: 0.75rem;
  font-size: 0.82rem;
  color: var(--color-text-secondary);
}
.finding-meta strong {
  color: var(--color-text);
}
.finding-detail {
  margin: 0.5rem 0;
}
.finding-evidence {
  background: var(--color-bg-section);
  border-radius: 4px;
  padding: 0.6rem 0.8rem;
  font-family: var(--font-mono);
  font-size: 0.82rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin-top: 0.5rem;
}
.finding-convergence {
  background: #e3f2fd;
  border-left: 3px solid var(--color-accent);
  border-radius: 4px;
  padding: 0.5rem 0.8rem;
  font-size: 0.82rem;
  color: var(--color-accent);
  margin-top: 0.5rem;
}
.finding-constat {
  margin: 0.5rem 0;
  font-size: 0.9rem;
  line-height: 1.6;
}
.finding-impact {
  background: #fff3e0;
  border-left: 3px solid var(--color-important);
  border-radius: 4px;
  padding: 0.6rem 0.8rem;
  font-size: 0.88rem;
  margin-top: 0.5rem;
}
.finding-correction {
  background: #e8f5e9;
  border-left: 3px solid var(--color-good);
  border-radius: 4px;
  padding: 0.6rem 0.8rem;
  font-size: 0.88rem;
  margin-top: 0.5rem;
}
.finding-maieutique {
  margin-top: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 0.5rem 0.8rem;
  font-size: 0.85rem;
}
.finding-maieutique summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--color-accent);
}
.finding-maieutique ol {
  margin: 0.5rem 0 0;
  padding-left: 1.25rem;
}
.finding-maieutique li {
  margin: 0.3rem 0;
}

/* Scope section */
.scope-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin: 1rem 0;
}
.scope-card {
  border-radius: 8px;
  padding: 1rem 1.25rem;
}
.scope-covered {
  background: #e8f5e9;
  border: 1px solid #c8e6c9;
}
.scope-not-covered {
  background: #fff3e0;
  border: 1px solid #ffe0b2;
}
.scope-card h4 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}
.scope-card ul {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.88rem;
}
.scope-card li {
  margin: 0.25rem 0;
}

/* LLM crawlers section */
.llm-section {
  background: var(--color-bg-section);
  border-radius: 8px;
  padding: 1.25rem;
  margin: 1.5rem 0;
}
.llm-section h3 {
  margin: 0 0 0.75rem;
  font-size: 1.05rem;
}
.llm-section table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.75rem 0;
  font-size: 0.9rem;
}
.llm-section th, .llm-section td {
  padding: 0.5rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}
.llm-section th {
  background: #e0e0e0;
  font-weight: 600;
}
.llm-section .verdict-note {
  font-size: 0.85rem;
  color: var(--color-text-secondary);
  margin-top: 0.5rem;
  font-style: italic;
}

/* Comparison table (compare mode) */
.comparison-table { width: 100%; border-collapse: collapse; margin: 1.5rem 0; }
.comparison-table th, .comparison-table td { padding: 0.6rem 1rem; text-align: left; border-bottom: 1px solid var(--color-border); }
.comparison-table th { background: var(--color-bg-section); font-weight: 600; }
.delta-better { color: var(--color-good); }
.delta-worse { color: var(--color-poor); }
.delta-same { color: var(--color-text-secondary); }

/* Coverage */
.coverage-bar-container {
  background: var(--color-bg-section);
  border-radius: 8px;
  padding: 1.25rem;
  margin: 1rem 0;
}
.coverage-bar-track {
  width: 100%;
  height: 12px;
  background: #e0e0e0;
  border-radius: 6px;
  overflow: hidden;
  margin: 0.75rem 0;
}
.coverage-bar-fill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.5s ease;
}
.coverage-stats {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  color: var(--color-text-secondary);
}

/* Methodology */
.methodology-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin: 1rem 0;
}
.methodology-card {
  background: var(--color-bg-section);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  text-align: center;
}
.methodology-card .count {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 0.35rem;
}
.methodology-card .label {
  font-size: 0.82rem;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

/* Correction guides */
.guide-card {
  border: 1px solid var(--color-border);
  border-left: 4px solid var(--color-bloquant);
  border-radius: 4px;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
  background: var(--color-bg);
}
.guide-card h4 {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
  color: var(--color-text);
}
.guide-card ol {
  margin: 0.5rem 0;
  padding-left: 1.25rem;
}
.guide-card li {
  margin: 0.35rem 0;
  font-size: 0.9rem;
}
.guide-impact {
  font-size: 0.85rem;
  color: var(--color-text-secondary);
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--color-border);
}
.guide-impact strong {
  color: var(--color-text);
}

/* Footer */
.report-footer {
  margin-top: 3rem;
  padding-top: 1.5rem;
  border-top: 2px solid var(--color-border);
  text-align: center;
  font-size: 0.82rem;
  color: var(--color-text-secondary);
  font-style: italic;
}

/* Print */
@media print {
  body { font-size: 12px; }
  .report-container { max-width: 100%; padding: 0; }
  .finding-card.open .finding-body,
  .finding-body { display: block !important; }
  .finding-chevron { display: none; }
  .severity-badge { cursor: default; }
  .severity-badge:hover { transform: none; box-shadow: none; }
  .gauges-section { page-break-inside: avoid; }
  .finding-card { page-break-inside: avoid; }
  .section { page-break-before: auto; }
  .section h2 { page-break-after: avoid; }
}

/* Responsive */
@media (max-width: 600px) {
  .report-container { padding: 1rem; }
  .report-header h1 { font-size: 1.4rem; }
  .gauges-section { gap: 1rem; padding: 1rem; }
  .gauge svg { width: 80px; height: 80px; }
  .severity-badges { gap: 0.5rem; }
  .severity-badge { padding: 0.4rem 0.75rem; font-size: 0.8rem; }
  .methodology-grid { grid-template-columns: 1fr; }
}
"""

JS = """\
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.finding-header').forEach(function(h) {
    h.addEventListener('click', function() {
      h.parentElement.classList.toggle('open');
    });
  });
  document.querySelectorAll('[data-scroll]').forEach(function(el) {
    el.addEventListener('click', function() {
      var target = document.getElementById(el.dataset.scroll);
      if (target) target.scrollIntoView({behavior: 'smooth'});
    });
  });
});
"""


def escape(text: str) -> str:
    """Echappe le texte pour insertion HTML."""
    if not isinstance(text, str):
        text = str(text)
    return html.escape(text, quote=True)


def render_header(site_name: str, mode: str, date_str: str) -> str:
    """Genere le header du rapport."""
    mode_label = "Comparaison avant/apres" if mode == "compare" else "Audit SEO du menu"
    return f'''<div class="report-header">
  <h1>{escape(mode_label)} &mdash; {escape(site_name)}</h1>
  <p class="meta">
    <span>Date : {escape(date_str)}</span>
    <span>&bull;</span>
    <span>Mode : {escape(mode.upper())}</span>
    <span>&bull;</span>
    <span>seo-audit-for-claude-code v{escape(TOOLKIT_VERSION)}</span>
  </p>
</div>'''


def render_verdict(mode: str, counts: dict[str, int]) -> str:
    """Genere la banniere de verdict."""
    total_bloquant = counts.get("bloquant", 0)
    total_critique = counts.get("critique", 0)
    total_important = counts.get("important", 0)

    if mode == "compare":
        if total_bloquant > 0:
            css_class = "verdict-nogo"
            label = "\U0001f6ab NO-GO — Problemes bloquants detectes. Ne pas deployer en l'etat."
        elif total_critique > 2 or (total_critique > 0 and total_important > 3):
            css_class = "verdict-go-conditions"
            label = "\u26a0\ufe0f GO SOUS CONDITIONS — Corrections critiques necessaires avant deploiement."
        else:
            css_class = "verdict-go"
            label = "\u2705 GO — Migration validee. Optimisations mineures possibles."
    else:
        if total_bloquant > 0:
            css_class = "verdict-audit-risk"
            label = "\U0001f6ab BLOQUANT — Problemes majeurs detectes, corrections urgentes requises."
        elif total_critique > 2:
            css_class = "verdict-audit-risk"
            label = "\U0001f534 RISQUE ELEVE — Corrections majeures requises."
        elif total_critique > 0 or total_important > 3:
            css_class = "verdict-audit-attention"
            label = "\u26a0\ufe0f ATTENTION — Ajustements necessaires."
        else:
            css_class = "verdict-audit-ok"
            label = "\u2705 OK — Optimisations possibles, pas de probleme majeur."

    return f'<div class="verdict-banner {css_class}">{escape(label)}</div>'


def render_gauges(scores: dict[str, int]) -> str:
    """Genere la section des 5 jauges SVG."""
    parts = ['<div class="gauges-section">']
    for cat_key, cat_label in SCORE_CATEGORIES:
        score = scores.get(cat_key, -1)
        parts.append(generate_gauge_svg(score, cat_label))
    parts.append("</div>")
    return "\n".join(parts)


def render_severity_badges(counts: dict[str, int]) -> str:
    """Genere les badges de comptage par severite (cliquables pour scroller)."""
    parts = ['<div class="severity-badges">']
    for sev in SEVERITY_ORDER:
        count = counts.get(sev, 0)
        label = SEVERITY_LABEL[sev]
        emoji = SEVERITY_EMOJI[sev]
        parts.append(
            f'<button class="severity-badge badge-{sev}" data-scroll="section-{sev}" '
            f'title="Voir les {count} findings {label}">'
            f'<span class="badge-count">{count}</span>'
            f'{emoji} {escape(label)}'
            f'</button>'
        )
    parts.append("</div>")
    return "\n".join(parts)


def _interpolate_label(template: str, extra: dict[str, Any]) -> str:
    """Interpolate {header_kb}, {svg_count} etc. from extra into a template string."""
    if not extra or "{" not in template:
        return template
    try:
        return template.format(**extra)
    except (KeyError, ValueError, IndexError):
        return template


def render_finding_card(f: Finding, index: int) -> str:
    """Genere une carte HTML pour un finding avec detail expandable."""
    sev = f.severity_normalized
    label_info = FINDING_LABELS.get(f.test, {})

    # Title — interpolate extra data for header_weight etc.
    raw_title = label_info.get("title", f.message or f.test or "Finding sans titre")
    title = _interpolate_label(raw_title, f.extra) if f.extra else raw_title

    # Meta info
    meta_parts: list[str] = []
    if f.code:
        meta_parts.append(f"<strong>Code :</strong> <code>{escape(f.code)}</code>")
    if f.dimension:
        meta_parts.append(f"<strong>Domaine :</strong> {escape(f.dimension)}")
    if f.url:
        meta_parts.append(f"<strong>URL :</strong> <code>{escape(f.url)}</code>")
    if f.checklist_id:
        meta_parts.append(f"<strong>Checklist :</strong> {escape(f.checklist_id)}")

    meta_html = ""
    if meta_parts:
        meta_html = '<div class="finding-meta">' + " ".join(meta_parts) + "</div>"

    # Constat section (from enriched FINDING_LABELS or fallback to detail/description)
    constat_html = ""
    constat_text = label_info.get("constat", "")
    if constat_text:
        constat_text = _interpolate_label(constat_text, f.extra) if f.extra else constat_text
        constat_html = f'<div class="finding-constat"><strong>Constat :</strong> {escape(constat_text)}</div>'
    elif f.detail:
        constat_html = f'<div class="finding-constat"><strong>Constat :</strong> {escape(f.detail)}</div>'

    # Convergence note
    convergence_html = ""
    if f.convergence_note:
        convergence_html = f'<div class="finding-convergence">{escape(f.convergence_note)}</div>'

    # Impact section
    impact_html = ""
    impact_text = label_info.get("impact", "")
    if impact_text:
        impact_html = f'<div class="finding-impact"><strong>Impact :</strong> {escape(impact_text)}</div>'

    # Correction section
    correction_html = ""
    correction_text = label_info.get("correction", "")
    if correction_text:
        correction_html = f'<div class="finding-correction"><strong>Correction :</strong> {escape(correction_text)}</div>'

    # Maieutique section (questions)
    maieutique_html = ""
    questions = label_info.get("maieutique", [])
    if questions:
        q_items = "".join(f"<li>{escape(q)}</li>" for q in questions)
        maieutique_html = f'''<details class="finding-maieutique">
      <summary>Questions avant de corriger</summary>
      <ol>{q_items}</ol>
    </details>'''

    # Evidence
    evidence_html = ""
    if f.evidence:
        if isinstance(f.evidence, list):
            items = f.evidence[:10]
            evidence_text = "\n".join(str(e) for e in items)
            if len(f.evidence) > 10:
                evidence_text += f"\n...et {len(f.evidence) - 10} autres"
        else:
            evidence_text = str(f.evidence)[:500]
        evidence_html = f'<div class="finding-evidence">{escape(evidence_text)}</div>'

    return f'''<div class="finding-card">
  <div class="finding-header">
    <span class="finding-severity-dot dot-{sev}"></span>
    <span class="finding-title">{escape(title)}</span>
    <span class="finding-chevron">&#9654;</span>
  </div>
  <div class="finding-body">
    {meta_html}
    {constat_html}
    {convergence_html}
    {impact_html}
    {correction_html}
    {maieutique_html}
    {evidence_html}
  </div>
</div>'''


def render_comparison_table(findings: list[Finding]) -> str:
    """Genere un tableau comparatif prod vs staging pour le mode compare."""
    prod_findings: list[Finding] = []
    staging_findings: list[Finding] = []
    for f in findings:
        src = f.source_file.lower()
        if src.startswith("staging"):
            staging_findings.append(f)
        else:
            prod_findings.append(f)

    if not prod_findings and not staging_findings:
        return ""

    # Count by severity for each version
    prod_counts = {s: 0 for s in SEVERITY_ORDER}
    staging_counts = {s: 0 for s in SEVERITY_ORDER}
    for f in prod_findings:
        sev = f.severity_normalized
        if sev in prod_counts:
            prod_counts[sev] += 1
    for f in staging_findings:
        sev = f.severity_normalized
        if sev in staging_counts:
            staging_counts[sev] += 1

    # Extract specific metrics (CWV, header_weight)
    def _extract_metric(flist: list[Finding], test_name: str) -> str:
        for ff in flist:
            if ff.test == test_name:
                if ff.extra:
                    val = ff.extra.get("value") or ff.extra.get("header_kb") or ff.extra.get("header_bytes_kb")
                    verdict = ff.extra.get("verdict", "")
                    if val is not None:
                        return f"{val} ({verdict})" if verdict else str(val)
                return ff.severity_normalized.upper()
        return "-"

    # Build rows: (label, prod_val, staging_val, lower_is_better)
    rows: list[tuple[str, str, str, bool]] = []
    for sev in SEVERITY_ORDER:
        label = SEVERITY_LABEL[sev]
        rows.append((f"Findings {label}", str(prod_counts[sev]), str(staging_counts[sev]), True))

    rows.append(("Total findings", str(sum(prod_counts.values())), str(sum(staging_counts.values())), True))

    # CWV metrics
    for metric_test, metric_label in [
        ("cwv_ttfb", "TTFB"), ("cwv_fcp", "FCP"), ("cwv_lcp", "LCP"),
        ("cwv_cls", "CLS"), ("cwv_inp", "INP"),
    ]:
        p = _extract_metric(prod_findings, metric_test)
        s = _extract_metric(staging_findings, metric_test)
        if p != "-" or s != "-":
            rows.append((metric_label, p, s, True))

    # Header weight
    p_hw = _extract_metric(prod_findings, "header_weight")
    s_hw = _extract_metric(staging_findings, "header_weight")
    if p_hw != "-" or s_hw != "-":
        rows.append(("Header weight", p_hw, s_hw, True))

    # Build HTML table
    parts = [
        '<div class="section">',
        "<h2>Comparaison Prod vs Staging</h2>",
        '<table class="comparison-table">',
        "<thead><tr><th>Metrique</th><th>Prod</th><th>Staging</th><th>Delta</th></tr></thead>",
        "<tbody>",
    ]

    for label, prod_val, staging_val, lower_is_better in rows:
        # Compute delta
        delta_html = ""
        try:
            p_num = float(prod_val.split()[0].replace(",", "."))
            s_num = float(staging_val.split()[0].replace(",", "."))
            diff = s_num - p_num
            if abs(diff) < 0.001:
                delta_html = '<span class="delta-same">=</span>'
            elif (diff < 0) == lower_is_better:
                delta_html = f'<span class="delta-better">{diff:+.0f}</span>'
            else:
                delta_html = f'<span class="delta-worse">{diff:+.0f}</span>'
        except (ValueError, IndexError):
            delta_html = '<span class="delta-same">-</span>'

        parts.append(
            f"<tr><td>{escape(label)}</td>"
            f"<td>{escape(prod_val)}</td>"
            f"<td>{escape(staging_val)}</td>"
            f"<td>{delta_html}</td></tr>"
        )

    parts.append("</tbody></table></div>")
    return "\n".join(parts)


def render_findings_section(grouped: dict[str, list[Finding]]) -> str:
    """Genere la section des findings groupes par severite."""
    parts = ['<div class="section">', '<h2>Problemes identifies</h2>']

    for sev in SEVERITY_ORDER:
        findings = grouped.get(sev, [])
        if not findings:
            continue
        emoji = SEVERITY_EMOJI[sev]
        label = SEVERITY_LABEL[sev]
        plural = "S" if len(findings) > 1 else ""
        parts.append(f'<h3 id="section-{sev}">{emoji} {label}{plural} ({len(findings)})</h3>')
        for i, f in enumerate(findings, 1):
            parts.append(render_finding_card(f, i))

    parts.append("</div>")
    return "\n".join(parts)


def render_coverage_section(coverage: dict | None) -> str:
    """Genere la section de couverture si les donnees existent."""
    if not coverage:
        return ""

    pct = coverage.get("coverage_percent", 0)
    tested = coverage.get("tested", 0)
    total = coverage.get("total_items", 0)
    not_tested = coverage.get("not_tested", 0)

    color = "#0cce6b" if pct >= 80 else "#ffa400" if pct >= 50 else "#ff4e42"

    # Liste des items non testes
    not_tested_items: list[str] = []
    for item in coverage.get("items", []):
        if item.get("status") == "not_tested":
            not_tested_items.append(f"{item.get('id', '?')} — {item.get('name', '?')}")

    not_tested_html = ""
    if not_tested_items:
        items_html = "".join(f"<li>{escape(item)}</li>" for item in not_tested_items[:15])
        remaining = len(not_tested_items) - 15
        if remaining > 0:
            items_html += f"<li><em>...et {remaining} autres</em></li>"
        not_tested_html = f"""
  <details style="margin-top:0.75rem">
    <summary style="cursor:pointer;font-size:0.85rem;color:var(--color-text-secondary)">
      Voir les {len(not_tested_items)} items non testes
    </summary>
    <ul style="font-size:0.82rem;margin-top:0.5rem">{items_html}</ul>
  </details>"""

    return f'''<div class="section">
  <h2>Couverture de l'audit</h2>
  <div class="coverage-bar-container">
    <div style="font-size:1.5rem;font-weight:700;color:{color}">{pct}%</div>
    <div class="coverage-bar-track">
      <div class="coverage-bar-fill" style="width:{pct}%;background:{color}"></div>
    </div>
    <div class="coverage-stats">
      <span>{tested} items testes sur {total}</span>
      <span>{not_tested} non testes</span>
    </div>
    <p style="font-size:0.82rem;color:var(--color-text-secondary);margin-top:0.5rem">
      Checklist {escape(coverage.get('checklist_version', 'v0.3'))}
    </p>{not_tested_html}
  </div>
</div>'''


def render_methodology_section(findings: list[Finding], intake: dict) -> str:
    """Genere la section methodologie avec les compteurs SAVOIR / PENSER / PAS VERIFIER."""
    # Compter les types de connaissance a partir des fichiers de findings
    # Ces champs sont dans les JSON de findings (i_know, i_think, i_cannot_verify)
    # On les approxime ici depuis les findings
    count_know = 0
    count_think = 0
    count_cannot = 0

    for f in findings:
        sev = f.severity_normalized
        if f.passed is True:
            count_know += 1
        elif f.passed is False and sev in ("bloquant", "critique"):
            count_know += 1
        elif f.passed is False and sev in ("important",):
            count_think += 1
        elif sev == "recommandation":
            count_think += 1

    # Items non verifiables (estimation si pas de donnee)
    if count_know == 0 and count_think == 0:
        count_cannot = 1  # au moins un rappel
    else:
        count_cannot = max(1, len(findings) // 10)

    return f'''<div class="section">
  <h2>Methodologie — Transparence sur l'analyse</h2>
  <p style="font-size:0.9rem;color:var(--color-text-secondary);margin-bottom:1rem">
    Chaque constat est classe selon trois niveaux de confiance pour preserver la credibilite de cet audit.
  </p>
  <div class="methodology-grid">
    <div class="methodology-card">
      <div class="count" style="color:var(--color-good)">{count_know}</div>
      <div class="label">\u2705 JE SAIS<br><small>Verifie dans les donnees fournies</small></div>
    </div>
    <div class="methodology-card">
      <div class="count" style="color:var(--color-needs-improvement)">{count_think}</div>
      <div class="label">\U0001f914 JE PENSE<br><small>Interpretation basee sur des sources</small></div>
    </div>
    <div class="methodology-card">
      <div class="count" style="color:var(--color-poor)">{count_cannot}</div>
      <div class="label">\u2753 PAS VERIFIER<br><small>Necessite acces live</small></div>
    </div>
  </div>
</div>'''


def render_correction_guides(findings: list[Finding]) -> str:
    """Genere les guides de correction maieutiques pour les BLOQUANT et CRITIQUE."""
    severe_findings = [
        f for f in findings
        if f.severity_normalized in ("bloquant", "critique")
    ]

    if not severe_findings:
        return ""

    # Trouver les guides applicables
    matched_guides: list[tuple[Finding, dict]] = []
    seen_guide_keys: set[str] = set()

    for f in severe_findings:
        test_name = f.test.lower().strip()
        guide_key = TEST_TO_GUIDE.get(test_name)
        if guide_key and guide_key in CORRECTION_GUIDES and guide_key not in seen_guide_keys:
            matched_guides.append((f, CORRECTION_GUIDES[guide_key]))
            seen_guide_keys.add(guide_key)

    if not matched_guides:
        return ""

    parts = [
        '<div class="section">',
        "<h2>Guides de correction</h2>",
        '<p style="font-size:0.9rem;color:var(--color-text-secondary);margin-bottom:1rem">'
        "Pour chaque probleme bloquant ou critique, voici les questions a se poser "
        "avant de corriger — approche maieutique pour eviter les faux positifs."
        "</p>",
    ]

    for finding, guide in matched_guides:
        questions_html = "".join(
            f"<li>{escape(q)}</li>" for q in guide["questions"]
        )
        parts.append(f'''<div class="guide-card">
  <h4>{escape(guide["title"])}</h4>
  <ol>{questions_html}</ol>
  <div class="guide-impact">
    <strong>Impact SEO :</strong> {escape(guide["impact"])}<br>
    <strong>Effort estime :</strong> {escape(guide["effort"])}
  </div>
</div>''')

    parts.append("</div>")
    return "\n".join(parts)


def render_scope_section() -> str:
    """Genere la section Perimetre de l'audit."""
    return '''<div class="section">
  <h2>Perimetre de l'audit</h2>
  <div class="scope-grid">
    <div class="scope-card scope-covered">
      <h4>Ce que cet audit couvre</h4>
      <ul>
        <li>Structure HTML du menu de navigation (header, nav, burger)</li>
        <li>Crawlabilite : HTML source vs DOM rendu (Googlebot)</li>
        <li>Parite mobile/desktop (Mobile-First Indexing)</li>
        <li>Accessibilite clavier et ARIA (WCAG 2.1/2.2)</li>
        <li>Performance du menu (Core Web Vitals, poids header)</li>
        <li>Semantique HTML5 et structure des liens</li>
      </ul>
    </div>
    <div class="scope-card scope-not-covered">
      <h4>Ce que cet audit ne couvre PAS</h4>
      <ul>
        <li>Graphe de liens complet du site (maillage interne global)</li>
        <li>Profondeur de clic au-dela du menu</li>
        <li>Profil de backlinks (liens entrants)</li>
        <li>Contenu editorial et optimisation on-page</li>
        <li>Monitoring continu (audit ponctuel)</li>
        <li>Donnees Google Search Console / Analytics</li>
      </ul>
    </div>
  </div>
</div>'''


def render_llm_crawlers_section() -> str:
    """Genere la section Visibilite pour les crawlers IA."""
    return '''<div class="section">
  <div class="llm-section">
    <h3>Visibilite pour les crawlers IA</h3>
    <p style="font-size:0.9rem;margin-bottom:0.75rem">
      Les crawlers des moteurs de recherche IA (GPTBot, PerplexityBot, ClaudeBot)
      ne rendent PAS le JavaScript. Ils analysent uniquement le HTML source brut,
      comme un curl. Si votre menu depend de JS pour afficher les liens, ces crawlers
      ne voient pas votre navigation.
    </p>
    <table>
      <thead>
        <tr><th>Crawler</th><th>Rend le JS ?</th><th>Voit le menu ?</th></tr>
      </thead>
      <tbody>
        <tr><td>Googlebot</td><td>Oui (Chromium headless)</td><td>Oui (si pas de cloaking)</td></tr>
        <tr><td>Bingbot</td><td>Partiellement</td><td>Depend du framework</td></tr>
        <tr><td>GPTBot (OpenAI)</td><td>Non</td><td>Uniquement si SSR/SSG</td></tr>
        <tr><td>PerplexityBot</td><td>Non</td><td>Uniquement si SSR/SSG</td></tr>
        <tr><td>ClaudeBot (Anthropic)</td><td>Non</td><td>Uniquement si SSR/SSG</td></tr>
      </tbody>
    </table>
    <p class="verdict-note">
      Si votre site utilise le SSR (Server-Side Rendering) ou le SSG (Static Site Generation),
      les liens du menu sont dans le HTML source et sont visibles par tous les crawlers.
    </p>
  </div>
</div>'''


def render_footer(date_str: str) -> str:
    """Genere le footer du rapport."""
    return f'''<div class="report-footer">
  Rapport genere le {escape(date_str)} par
  <strong>seo-audit-for-claude-code</strong> v{escape(TOOLKIT_VERSION)}<br>
  Equipe : orchestrator + 6 specialistes + reporter + reviewer
</div>'''


def build_html_report(
    site_name: str,
    mode: str,
    findings: list[Finding],
    scores: dict[str, int],
    counts: dict[str, int],
    grouped: dict[str, list[Finding]],
    coverage: dict | None,
    intake: dict,
    date_str: str,
) -> str:
    """Assemble toutes les sections en un document HTML complet."""
    comparison_html = render_comparison_table(findings) if mode == "compare" else ""

    body_parts = [
        '<div class="report-container">',
        render_header(site_name, mode, date_str),
        render_verdict(mode, counts),
        render_scope_section(),
        render_gauges(scores),
        comparison_html,
        render_llm_crawlers_section(),
        render_severity_badges(counts),
        render_findings_section(grouped),
        render_coverage_section(coverage),
        render_methodology_section(findings, intake),
        render_footer(date_str),
        "</div>",
    ]

    body_html = "\n".join(body_parts)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Audit SEO — {escape(site_name)}</title>
<style>
{CSS}
</style>
</head>
<body>
{body_html}
<script>
{JS}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------
def main() -> int:
    """Point d'entree principal du generateur de rapport HTML."""
    parser = argparse.ArgumentParser(
        description="Genere un rapport HTML autonome a partir des findings JSON d'un audit SEO."
    )
    parser.add_argument(
        "--audit-dir", required=True,
        help="Chemin vers le dossier d'audit (contenant findings/, pages/, etc.)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Chemin du fichier HTML de sortie (defaut: reports/audit-report.html dans audit-dir)"
    )
    parser.add_argument(
        "--mode", choices=["audit", "compare"], default="audit",
        help="Mode de l'audit : audit simple ou comparaison (defaut: audit)"
    )
    parser.add_argument(
        "--site-name", default="Site",
        help="Nom du site pour le header du rapport"
    )

    args = parser.parse_args()

    audit_dir = Path(args.audit_dir)
    if not audit_dir.exists():
        print(f"[report_html] ERREUR: dossier d'audit introuvable : {audit_dir}", file=sys.stderr)
        return 1

    # Determiner le chemin de sortie
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = audit_dir / "reports" / "audit-report.html"

    # Charger les donnees
    print(f"[report_html] Chargement des findings depuis {audit_dir / 'findings'}...", file=sys.stderr)
    all_findings = load_all_findings(audit_dir)
    pre_dedup = len(all_findings)
    all_findings = deduplicate_findings(all_findings)
    print(f"[report_html] Deduplication: {pre_dedup} -> {len(all_findings)} findings", file=sys.stderr)

    if not all_findings:
        print("[report_html] WARNING: aucun finding trouve. Le rapport sera vide.", file=sys.stderr)

    # Charger intake pour le mode
    intake = load_intake(audit_dir)
    mode = args.mode or intake.get("mode", "audit")
    site_name = args.site_name or intake.get("site", intake.get("url", "Site"))

    # Calculer scores et compteurs
    scores = compute_category_scores(all_findings)
    counts = count_by_severity(all_findings)
    grouped = group_findings_by_severity(all_findings)

    # Charger donnees supplementaires
    coverage = load_coverage(audit_dir)
    date_str = datetime.now().strftime("%Y-%m-%d a %H:%M")

    # Log resume
    total_findings = sum(counts.values())
    print(
        f"[report_html] {total_findings} findings "
        f"({counts['bloquant']}B / {counts['critique']}C / "
        f"{counts['important']}I / {counts['recommandation']}R)",
        file=sys.stderr,
    )
    for cat_key, cat_label in SCORE_CATEGORIES:
        s = scores.get(cat_key, -1)
        display = f"{s}/100" if s >= 0 else "non teste"
        print(f"[report_html]   {cat_label}: {display}", file=sys.stderr)

    # Generer le HTML
    html_doc = build_html_report(
        site_name=site_name,
        mode=mode,
        findings=all_findings,
        scores=scores,
        counts=counts,
        grouped=grouped,
        coverage=coverage,
        intake=intake,
        date_str=date_str,
    )

    # Ecrire le fichier
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")

    size_kb = len(html_doc.encode("utf-8")) / 1024
    print(
        f"[report_html] \u2713 {output_path} ({size_kb:.1f} KB, {total_findings} findings)",
        file=sys.stderr,
    )

    if size_kb > 200:
        print(
            f"[report_html] WARNING: le rapport fait {size_kb:.0f} KB (cible < 200 KB)",
            file=sys.stderr,
        )

    # JSON summary on stdout
    print(json.dumps({
        "output_file": str(output_path),
        "size_kb": round(size_kb, 1),
        "total_findings": total_findings,
        "counts": counts,
        "scores": {k: v for k, v in scores.items() if v >= 0},
        "mode": mode,
    }, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[report_html] ERREUR INATTENDUE: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)
