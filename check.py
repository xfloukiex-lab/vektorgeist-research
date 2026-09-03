"""Build-time gate for the research index. Run BEFORE any publish.

    python check.py            -> exit 0 clean, 1 on any finding

Scrubs the BUILT artifact (docs/index.html), not the source, because the built
file is what a reader receives. Every check runs against a CONTROL string that
must be present -- a scan that cannot prove it is looking is a scan that can
return a false all-clear.

What it halts on:
  * a developer path or the dev account name baked into the page
  * a credential-shaped literal
  * the operator's personal address (the papers carry a contact by design; this
    index does not need one, so any occurrence here is unintended)
  * a link to a surface that does not exist yet -- a dead link on a research
    index is worse than a missing one
  * a DOI on the page that is not one of the ten published concept DOIs
  * any paper missing from the page
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE = HERE / "docs" / "index.html"
MANIFEST = HERE / "manifest.json"

# CONTROL: must appear in the built page, else the extractor is dead and every
# "0 hits" below is meaningless.
CONTROL = "Hodos"

BANNED = [
    ("dev path", re.compile(r"C:[\\/]Users[\\/]", re.I)),
    ("dev account name", re.compile(r"\bAlexa\b")),
    ("unix home path", re.compile(r"/home/[a-z0-9_-]+/", re.I)),
    ("file:// url", re.compile(r"file://", re.I)),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}")),
    ("aws key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key header", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("bearer literal", re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")),
    ("personal address", re.compile(r"xfloukiex@", re.I)),
    ("localhost", re.compile(r"127\.0\.0\.1|localhost:\d+")),
    ("raw ip", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
    # Persona / private-conversation class. A published page carries the work,
    # never the people who made it or anything about what anyone said. The
    # 2026-08-02 leak reached a live Pages site through exactly this pipeline:
    # commentary written into a manifest, rendered by a build script, served.
    ("operator handle", re.compile(r"\bFlouk\b")),
    ("agent name", re.compile(r"\bVanta\b")),
    ("collaborator name", re.compile(r"\bElif\b|\bHolohydra\b|\bElifterminal\b", re.I)),
    ("attributed quotation", re.compile(r"[\"'“][^\"'”]{0,140}[\"'”]\s*[-–—]\s*[A-Z]")),
    ("said/asked/felt narration", re.compile(
        r"\b(?:he|she|they|the owner)\s+(?:said|asked|told|wanted|was\s+(?:angry|right|wrong))\b", re.I)),
    ("caught-by attribution", re.compile(r"\bcaught by\b", re.I)),
]

# The only external surfaces this page may link to. A link to anything else is
# either a typo or a page that does not exist -- both halt the build.
ALLOWED_URLS = {
    "https://xfloukiex-lab.github.io/hodos-study/",
    "https://xfloukiex-lab.github.io/cordthym-study/",
    "https://xfloukiex-lab.github.io/vgm-math/",
}


def main() -> int:
    if not PAGE.exists():
        print(f"FAIL: no built page at {PAGE} -- run build.py first", file=sys.stderr)
        return 1

    html = PAGE.read_text(encoding="utf-8")
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems: list[str] = []

    # --- control ----------------------------------------------------------
    if CONTROL not in html:
        print(f"FAIL: CONTROL string {CONTROL!r} absent -- the scan is dead, "
              f"its clean result means nothing", file=sys.stderr)
        return 1
    print(f"control  : {CONTROL!r} present ({html.count(CONTROL)}x) -- scan is live")

    # --- leak scrub -------------------------------------------------------
    for label, pat in BANNED:
        hits = pat.findall(html)
        if hits:
            problems.append(f"{label}: {len(hits)} hit(s) -- e.g. {hits[0]!r}")
    print(f"scrub    : {len(BANNED)} patterns, "
          f"{sum(1 for lbl, p in BANNED if p.search(html))} tripped")

    # --- links ------------------------------------------------------------
    urls = set(re.findall(r'href="(https?://[^"]+)"', html))
    doi_urls = {u for u in urls if u.startswith("https://doi.org/")}
    other = urls - doi_urls
    for u in sorted(other - ALLOWED_URLS):
        problems.append(f"link to a surface not on the allowlist: {u}")
    print(f"links    : {len(doi_urls)} DOI, {len(other)} other "
          f"({len(other - ALLOWED_URLS)} not allowlisted)")

    # --- DOIs match the manifest, and every paper is on the page ----------
    expected = {p["doi"] for p in m["papers"]}
    expected.add(m["premise"]["origin_doi"])
    expected.add(m["premise"]["own_doi"])
    on_page = {u.rsplit("/", 2)[-2] + "/" + u.rsplit("/", 1)[-1]
               for u in doi_urls}
    on_page = {u[len("https://doi.org/"):] for u in doi_urls}
    stray = on_page - expected
    missing = expected - on_page
    if stray:
        problems.append(f"DOI on page not in manifest: {sorted(stray)}")
    if missing:
        problems.append(f"manifest DOI missing from page: {sorted(missing)}")

    # Every paper name must appear, or the page silently dropped one.
    for p in m["papers"]:
        if p["name"].split(":")[0] not in html:
            problems.append(f"paper missing from page: {p['name']}")
    print(f"papers   : {len(m['papers'])} in manifest, "
          f"{len(on_page)} distinct DOIs on page")

    # --- the withdrawn wording must not reappear --------------------------
    # These are claims corrected at their published surface. If either phrasing
    # shows up here, this page would be re-publishing a superseded claim.
    for phrase in ("relational and lossy", "lossier than simply using",
                   "3-16x", "3–16×", "structural rather than fixable"):
        if phrase.lower() in html.lower():
            problems.append(f"superseded wording present: {phrase!r}")
    print("withdrawn: 5 superseded phrasings checked")

    if problems:
        print("\nHALT -- build is not shippable:", file=sys.stderr)
        for p in problems:
            print(f"  * {p}", file=sys.stderr)
        return 1

    print(f"\nok: {PAGE} clean ({len(html):,} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
