"""Build the Vektorgeist research index from manifest.json.

    python build.py            -> docs/index.html

The MANIFEST is the single source of truth. Every count on the page is generated
from it, so the summary cannot drift out of date -- the same rule the hodos and
cordthym study records are built on, and the reason those two cannot disagree
with their own data.

Palette and typography are deliberately identical to the study records
(`#f5f1e8` paper, `#fffdf8` card, `#e0d7c6` rule, `#221f1a` ink, `#2d5a78`
accent, serif headings) so the whole public record reads as one body of work.

Self-contained output: no CDN, no external font, no script. It is an index, and
an index that cannot render offline is worse than a plain list.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
OUT = HERE / "docs" / "index.html"

CSS = """
:root{
  --bg:#f5f1e8; --panel:#fffdf8; --line:#e0d7c6; --ink:#221f1a; --dim:#6e665a;
  --ok:#2f6b4a; --part:#8f6415; --no:#a3392c; --acc:#2d5a78;
  --slab:#efe9dc; --warn:#f6e7e2;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.65 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:0 22px 90px}
header{border-bottom:1px solid var(--line);padding:38px 0 22px;margin-bottom:26px}
h1{margin:0 0 6px;font:600 32px/1.2 var(--serif);letter-spacing:-.2px}
.sub{color:var(--dim);margin:0 0 6px;font-size:16px}
.byline{color:var(--dim);font-size:13px;margin:10px 0 0}
.notice{background:var(--warn);border:1px solid #d8b3aa;color:#7d2f24;
  padding:11px 14px;border-radius:7px;font-size:13.5px;margin:20px 0 0}
h2{font:600 22px/1.3 var(--serif);margin:38px 0 12px;padding-bottom:8px;
  border-bottom:1px solid var(--line)}
h2:first-of-type{margin-top:8px}
.lede{font-size:16.5px}
.premise{background:var(--panel);border:1px solid var(--line);border-radius:9px;
  padding:20px 22px;margin:0 0 18px;box-shadow:0 1px 2px rgba(60,50,35,.05)}
.premise .stmt{font:600 18px/1.5 var(--serif);margin:0 0 12px}
.premise .meta{color:var(--dim);font-size:13px;margin:10px 0 0}
table{width:100%;border-collapse:collapse;margin:0 0 20px;font-size:14px}
th,td{text-align:left;padding:9px 11px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.4px}
.tag{font-size:11px;padding:2px 9px;border-radius:20px;border:1px solid;white-space:nowrap;
  text-transform:uppercase;letter-spacing:.4px;font-weight:600}
.tag.ok{color:var(--ok);border-color:var(--ok)}
.tag.part{color:var(--part);border-color:var(--part)}
.tag.no{color:var(--no);border-color:var(--no)}
.p{border:1px solid var(--line);background:var(--panel);border-radius:9px;padding:19px 21px;
  margin:0 0 16px;box-shadow:0 1px 2px rgba(60,50,35,.05)}
.p h3{margin:0 0 4px;font:600 18px/1.35 var(--serif)}
.p .q{color:var(--dim);font-style:italic;margin:0 0 11px;font-size:14.5px}
.lab{color:var(--dim);font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;
  margin:13px 0 3px}
.p p{margin:0}
.p .lim{border-left:3px solid var(--line);padding-left:13px;margin-top:5px;color:var(--dim)}
.doi{margin:14px 0 0;font-size:13px}
.doi code{background:var(--slab);padding:2px 6px;border-radius:4px;font-size:12.5px}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin:0 0 18px}
.chip{border:1px solid var(--line);border-radius:20px;padding:4px 13px;font-size:13px;
  background:var(--panel)}
.lane{border:1px solid var(--line);background:var(--panel);border-radius:9px;
  padding:16px 19px;margin:0 0 14px}
.lane h3{margin:0 0 5px;font:600 16px/1.35 var(--serif)}
.lane .care{background:var(--warn);border-left:3px solid var(--no);padding:9px 13px;
  margin:11px 0 0;border-radius:0 6px 6px 0;font-size:13.5px;color:#7d2f24}
.bound{background:var(--slab);border:1px solid var(--line);border-radius:9px;padding:17px 20px}
.bound ul{margin:8px 0 0;padding-left:20px} .bound li{margin:5px 0}
a{color:var(--acc)}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);
  color:var(--dim);font-size:13px}
"""


def esc(s: str) -> str:
    return html.escape(str(s), quote=False)


def rich(s: str) -> str:
    """Escape, then allow **bold** and `code` only. No raw HTML from the manifest."""
    s = esc(s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def doi_link(doi: str) -> str:
    return f'<a href="https://doi.org/{esc(doi)}">{esc(doi)}</a>'


def main() -> int:
    if not MANIFEST.exists():
        print(f"FAIL: no manifest at {MANIFEST}", file=sys.stderr)
        return 1
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))

    papers = m["papers"]
    equations = m["equations"]

    # Counts are GENERATED, never written down -- the summary cannot go stale.
    n_papers = len(papers)
    n_cleared = sum(1 for e in equations if e["state"] == "cleared")
    n_partial = sum(1 for e in equations if e["state"] == "partial")
    n_not = sum(1 for e in equations if e["state"] == "not-cleared")

    P = []
    A = P.append
    A(f'<h1>{esc(m["title"])}</h1>')
    A(f'<p class="sub">{esc(m["subtitle"])}</p>')
    A(f'<p class="byline">{esc(m["byline"])}</p>')
    if m.get("notice"):
        A(f'<div class="notice">{rich(m["notice"])}</div>')
    header = "\n".join(P)

    B = []
    A = B.append

    A(f'<p class="lede">{rich(m["lede"])}</p>')

    # --- the premise -------------------------------------------------------
    pr = m["premise"]
    A("<h2>The premise</h2>")
    A('<div class="premise">')
    A(f'<p class="stmt">{rich(pr["statement"])}</p>')
    A(f'<p>{rich(pr["gloss"])}</p>')
    A(f'<p class="meta">First published {esc(pr["origin_date"])} as part of '
      f'{esc(pr["origin_in"])} &middot; {doi_link(pr["origin_doi"])}<br>'
      f'Named {esc(pr["named_date"])}. {rich(pr["naming_note"])}<br>'
      f'Stated on its own account: {doi_link(pr["own_doi"])}</p>')
    A("</div>")

    # --- the equations -----------------------------------------------------
    A("<h2>The equations it generates</h2>")
    A(f'<p>{rich(m["equations_lede"])}</p>')
    A("<table><thead><tr><th>Name</th><th>The question it answers</th>"
      "<th>Where it stands</th></tr></thead><tbody>")
    cls = {"cleared": "ok", "partial": "part", "not-cleared": "no"}
    for e in equations:
        A(f'<tr><td><strong>{esc(e["name"])}</strong><br>'
          f'<span style="color:var(--dim);font-size:12.5px">{esc(e["greek"])}</span></td>'
          f'<td>{rich(e["question"])}</td>'
          f'<td><span class="tag {cls[e["state"]]}">{esc(e["state_label"])}</span><br>'
          f'<span style="font-size:13px">{rich(e["detail"])}</span></td></tr>')
    A("</tbody></table>")
    A(f'<p style="color:var(--dim);font-size:13.5px">Of the four, '
      f'<strong>{n_cleared}</strong> cleared every criterion fixed for them, '
      f'<strong>{n_partial}</strong> clears four of five and is not claimed as finished, and '
      f'<strong>{n_not}</strong> did not clear. '
      f'{rich(m["equations_note"])}</p>')

    # --- where it has been measured ---------------------------------------
    A("<h2>Where it has been measured</h2>")
    A('<div class="chips">')
    for d in m["domains"]:
        A(f'<span class="chip">{esc(d)}</span>')
    A("</div>")
    A(f'<p>{rich(m["domains_note"])}</p>')

    # --- the papers --------------------------------------------------------
    A(f'<h2>The papers &mdash; all {n_papers}</h2>')
    A(f'<p>{rich(m["papers_lede"])}</p>')
    for p in papers:
        A('<div class="p">')
        A(f'<h3>{esc(p["name"])}</h3>')
        A(f'<p class="q">{rich(p["asks"])}</p>')
        A('<p class="lab">What it found</p>')
        A(f'<p>{rich(p["found"])}</p>')
        A('<p class="lab">What it does not claim</p>')
        A(f'<p class="lim">{rich(p["limit"])}</p>')
        A(f'<p class="doi">{doi_link(p["doi"])}</p>')
        A("</div>")

    # --- the record --------------------------------------------------------
    A("<h2>The working record</h2>")
    A(f'<p>{rich(m["record"]["blurb"])}</p>')
    A(f'<p><a href="{esc(m["record"]["url"])}">{esc(m["record"]["url"])}</a></p>')

    # --- lanes -------------------------------------------------------------
    A("<h2>Work built on this engine</h2>")
    A(f'<p>{rich(m["lanes_lede"])}</p>')
    for ln in m["lanes"]:
        A('<div class="lane">')
        A(f'<h3>{esc(ln["name"])}</h3>')
        A(f'<p>{rich(ln["blurb"])}</p>')
        if ln.get("url"):
            A(f'<p style="margin-top:9px"><a href="{esc(ln["url"])}">{esc(ln["url"])}</a></p>')
        if ln.get("caveat"):
            A(f'<div class="care">{rich(ln["caveat"])}</div>')
        A("</div>")

    # --- boundary ----------------------------------------------------------
    A("<h2>What this is not</h2>")
    A('<div class="bound"><ul>')
    for b in m["boundary"]:
        A(f"<li>{rich(b)}</li>")
    A("</ul></div>")

    body = "\n".join(B)

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(m["title"])}</title>
<meta name="description" content="{esc(m["subtitle"])}">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
{header}
</header>
{body}
<footer>{rich(m["footer"])}</footer>
</div>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"ok: {OUT} ({len(doc):,} B) -- {n_papers} papers, "
          f"{n_cleared} cleared / {n_partial} partial / {n_not} not cleared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
