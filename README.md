# seo-audit-for-claude-code

**Technical SEO audit toolkit for Claude Code.** Multi-agent architecture with specialized skills — each audit runs like a consulting team: a maieutic project lead, technical specialists, a senior editor, and a QA reviewer.

> Built by [Kōeki Agency](https://koeki.fr) for SEO consultants who want repeatable, evidence-based audits with a clear audit trail.

---

## What makes it different

Most SEO audit tools crawl your site and dump 300 issues color-coded. They don't know your context, they can't compare an old menu to a new one before deployment, and they produce reports nobody reads.

This toolkit runs audits as a **collaboration between specialized agents**, coordinated by an orchestrator that actually **talks to you** before doing anything. Each specialist has narrow expertise (semantic HTML, link equity, crawlability, accessibility, performance, information architecture), their findings are consolidated, a senior editor writes the report, and a QA reviewer challenges it before delivery.

Every claim in the final report is tagged: **I KNOW** (verified in the data), **I THINK** (interpretation from a documented source), or **I CANNOT VERIFY** (needs live access). That's what separates a serious audit from a bullshit one.

No live site access required. The fetcher handles public URLs via `curl`, JS-heavy SPAs and authenticated staging environments via Playwright MCP.

## Quickstart

```bash
git clone https://github.com/agencekoeki/seo-audit-for-claude-code.git
cd seo-audit-for-claude-code
claude
```

Then in Claude Code, type:

```
/audit-menu
```

The orchestrator will interview you about what you need (single audit vs before/after comparison, URLs, authentication, specific pages to check) and coordinate the audit end-to-end.

## The team

The audit runs as 10 specialized roles working in coordination:

**Coordination**
- `orchestrator` — Maieutic project lead. Interviews you, dispatches work, consolidates findings.
- `reporter` — Senior editor. Turns technical findings into a readable client report.
- `reviewer` — QA / devil's advocate. Challenges every verdict before delivery.

**Technical specialists**
- `fetcher` — Data acquisition. Handles public URLs, authenticated pages, JS-rendered SPAs.
- `semantic` — HTML5 & ARIA expert. `<nav>`, `<ul>/<li>`, accessibility attributes.
- `link-equity` — Internal linking analyst. Google patents, PageRank distribution, dilution.
- `crawlability` — Crawl & rendering specialist. HTML source vs DOM after JS.
- `accessibility` — Mobile-first & WCAG 2.1/2.2.
- `performance` — Core Web Vitals impact of navigation (INP, CLS, LCP).
- `architecture` — Information architecture, user journey, content silos.

Each specialist has its own context, its own tool permissions, and its own knowledge base. They communicate via structured JSON findings.

## Two modes

**Audit mode** — Diagnose an existing menu. Each specialist analyzes their dimension. Consolidated report with verdicts.

**Comparison mode** — Validate a menu redesign against the current one. The comparator flags: removed URLs (orphan risk), depth changes, anchor text shifts, semantic regressions. Critical for pre-deployment gating.

## Philosophy

**Local-first.** No SaaS, no tracking. Python 3.10+ standard library.
**Evidence-based.** Every rule traces to a primary source: Google patents (Reasonable Surfer US 7,716,225, Boilerplate Detection US 8,898,296), Web.dev CWV documentation, WCAG specs.
**Maieutic over mechanical.** The orchestrator talks to you. It asks, reformulates, confirms.
**Honest about limits.** Every report lists what was checked, interpreted, or couldn't be verified.

## Requirements

- Claude Code ≥ 2.x (subagents support required)
- Python 3.10+
- Playwright MCP (optional — for authenticated/JS-heavy sites)

## Structure

```
seo-audit-for-claude-code/
├── CLAUDE.md                 # Instructions for Claude Code
├── .claude/
│   ├── agents/               # The 10 specialized roles
│   ├── skills/               # Reusable expertise with scripts + references
│   └── commands/
│       └── audit-menu.md     # /audit-menu entry point
├── shared/                   # Shared Python modules
├── knowledge/                # Global SEO knowledge base
├── audits/                   # Outputs (one folder per audit, gitignored)
└── tests/
```

See [CLAUDE.md](./CLAUDE.md) for the detailed architecture.

## License

MIT

## Author

**Sébastien Grillot** — Kōeki Agency. SEO since 2008.
