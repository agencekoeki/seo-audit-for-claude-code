#!/usr/bin/env python3
"""
md_to_html.py — Convertit un rapport Markdown en HTML autonome.

Stdlib only. Pas de dépendance externe (pas de mistune, markdown, etc.).
Gère un sous-ensemble de Markdown suffisant pour nos rapports :
- Titres # ## ### ####
- Gras **x** / italique *x*
- Listes - et 1. 2.
- Code `inline` et ```blocs```
- Tables GFM (pipe-delimited)
- Citations >
- Liens [text](url)
- Règles horizontales ---

Usage :
    python3 md_to_html.py --input report.md --output report.html
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import datetime
from pathlib import Path


CSS = """
:root {
  --color-text: #1a1a1a;
  --color-muted: #6b7280;
  --color-bg: #ffffff;
  --color-accent: #2563eb;
  --color-border: #e5e7eb;
  --color-code-bg: #f3f4f6;
  --color-blocking: #dc2626;
  --color-critical: #ea580c;
  --color-important: #ca8a04;
  --color-recommendation: #059669;
}

* { box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  font-size: 16px;
  line-height: 1.6;
  color: var(--color-text);
  background: var(--color-bg);
  max-width: 860px;
  margin: 2rem auto;
  padding: 0 1.5rem;
}

h1, h2, h3, h4 {
  line-height: 1.25;
  margin-top: 2rem;
  margin-bottom: 0.75rem;
  font-weight: 600;
}

h1 {
  font-size: 2rem;
  border-bottom: 2px solid var(--color-border);
  padding-bottom: 0.5rem;
}

h2 {
  font-size: 1.5rem;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 0.3rem;
}

h3 { font-size: 1.2rem; }
h4 { font-size: 1.05rem; color: var(--color-muted); }

p { margin: 0.75rem 0; }

ul, ol {
  margin: 0.75rem 0;
  padding-left: 1.5rem;
}

li { margin: 0.2rem 0; }

code {
  background: var(--color-code-bg);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  font-family: 'SF Mono', Menlo, Consolas, 'Courier New', monospace;
  font-size: 0.9em;
}

pre {
  background: var(--color-code-bg);
  padding: 1rem;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 0.9em;
  line-height: 1.4;
}

pre code {
  background: transparent;
  padding: 0;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 0.95em;
}

th, td {
  padding: 0.5rem 0.75rem;
  text-align: left;
  border: 1px solid var(--color-border);
}

th {
  background: var(--color-code-bg);
  font-weight: 600;
}

blockquote {
  border-left: 4px solid var(--color-border);
  padding: 0.25rem 1rem;
  margin: 1rem 0;
  color: var(--color-muted);
}

hr {
  border: 0;
  border-top: 1px solid var(--color-border);
  margin: 2rem 0;
}

a {
  color: var(--color-accent);
  text-decoration: none;
}

a:hover { text-decoration: underline; }

strong { font-weight: 600; }

/* Sévérité classes pour couleur des titres */
h3:has-text("BLOQUANT"), h2:has-text("BLOQUANT") { color: var(--color-blocking); }

/* Footer */
.footer-note {
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border);
  color: var(--color-muted);
  font-size: 0.875em;
  font-style: italic;
}

@media print {
  body { max-width: 100%; margin: 0; padding: 0; }
  h2, h3 { page-break-after: avoid; }
  pre, table { page-break-inside: avoid; }
}
"""


def escape_html(text: str) -> str:
    return html.escape(text, quote=False)


def inline_format(text: str) -> str:
    """Applique les transformations inline Markdown → HTML."""
    # Code inline `x` (avant escape pour préserver l'intérieur)
    code_blocks: list[str] = []
    def save_code(m):
        idx = len(code_blocks)
        code_blocks.append(m.group(1))
        return f"\x00CODE{idx}\x00"
    text = re.sub(r"`([^`]+)`", save_code, text)

    text = escape_html(text)

    # Gras **x**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # Italique *x*
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    # Liens [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # Restore code
    def restore_code(m):
        idx = int(m.group(1))
        return f"<code>{escape_html(code_blocks[idx])}</code>"
    text = re.sub(r"\x00CODE(\d+)\x00", restore_code, text)

    return text


def md_to_html(md: str) -> str:
    """Conversion minimaliste Markdown → HTML (sous-ensemble suffisant)."""
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)

    in_code_block = False
    code_lang = ""
    code_buffer: list[str] = []

    while i < n:
        line = lines[i]

        # Blocs code ```
        if line.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lang = line[3:].strip()
                code_buffer = []
            else:
                in_code_block = False
                code_content = "\n".join(code_buffer)
                out.append(f'<pre><code class="lang-{escape_html(code_lang)}">{escape_html(code_content)}</code></pre>')
            i += 1
            continue

        if in_code_block:
            code_buffer.append(line)
            i += 1
            continue

        # Hr
        if re.match(r"^---+\s*$", line) or re.match(r"^\*\*\*+\s*$", line):
            out.append("<hr/>")
            i += 1
            continue

        # Headings
        h_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if h_match:
            level = len(h_match.group(1))
            content = inline_format(h_match.group(2).rstrip())
            out.append(f"<h{level}>{content}</h{level}>")
            i += 1
            continue

        # Tables GFM
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s\-|:]+\|?\s*$", lines[i + 1]):
            # Table detected
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2  # skip separator
            rows = []
            while i < n and "|" in lines[i]:
                row_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(row_cells)
                i += 1

            out.append("<table>")
            out.append("<thead><tr>")
            for cell in header_cells:
                out.append(f"<th>{inline_format(cell)}</th>")
            out.append("</tr></thead>")
            out.append("<tbody>")
            for row in rows:
                out.append("<tr>")
                for cell in row:
                    out.append(f"<td>{inline_format(cell)}</td>")
                out.append("</tr>")
            out.append("</tbody></table>")
            continue

        # Listes non ordonnées
        if re.match(r"^\s*[-*+]\s+", line):
            list_items = []
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                content = re.sub(r"^\s*[-*+]\s+", "", lines[i])
                list_items.append(inline_format(content))
                i += 1
            out.append("<ul>")
            for item in list_items:
                out.append(f"<li>{item}</li>")
            out.append("</ul>")
            continue

        # Listes ordonnées
        if re.match(r"^\s*\d+\.\s+", line):
            list_items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                content = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                list_items.append(inline_format(content))
                i += 1
            out.append("<ol>")
            for item in list_items:
                out.append(f"<li>{item}</li>")
            out.append("</ol>")
            continue

        # Citation
        if line.startswith(">"):
            quote_lines = []
            while i < n and lines[i].startswith(">"):
                quote_lines.append(lines[i][1:].strip())
                i += 1
            out.append(f"<blockquote>{inline_format(' '.join(quote_lines))}</blockquote>")
            continue

        # Ligne vide
        if line.strip() == "":
            i += 1
            continue

        # Paragraphe : accumuler les lignes jusqu'à une ligne vide
        para_lines = [line]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#{1,6}|---+|\*\*\*+|```|>|\s*[-*+]\s|\s*\d+\.\s)", lines[i]):
            para_lines.append(lines[i])
            i += 1
        para_content = " ".join(para_lines)
        out.append(f"<p>{inline_format(para_content)}</p>")

    return "\n".join(out)


def wrap_html(body: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape_html(title)}</title>
<style>{CSS}</style>
</head>
<body>
{body}
<div class="footer-note">
Rapport généré le {datetime.now().strftime('%Y-%m-%d à %H:%M')} par seo-audit-for-claude-code.
</div>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Markdown report to standalone HTML")
    parser.add_argument("--input", required=True, help="Input Markdown file")
    parser.add_argument("--output", required=True, help="Output HTML file")
    parser.add_argument("--title", default="Audit SEO — Rapport", help="HTML title")

    args = parser.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"[md_to_html] ERROR: input not found: {src}", file=sys.stderr)
        return 1

    md = src.read_text(encoding="utf-8")
    body = md_to_html(md)
    html_doc = wrap_html(body, args.title)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    print(f"[md_to_html] ✓ {out} ({len(html_doc)} chars)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
