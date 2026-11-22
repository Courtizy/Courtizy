"""Draw the profile README's two preview cards from what each model already publishes.

Every number comes from the model's own exported JSON (the same files the hub's homepage previews read);
nothing is calculated here except placing it on the card. Writes a light and a dark SVG per model into
previews/, and the README picks one with <picture>.

    python3 scripts/render_previews.py                      # read the live site (what the workflow runs)
    python3 scripts/render_previews.py --valuation-data ../valuation/site/data \
        --tps-data ../TPS-Monte-Carlo-Simulation/site/data  # read local exports instead

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import urllib.request
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "previews"
SITE = "https://courtizy.github.io/"
VAL_TICKER = "AAPL"   # the company the Valuation app opens on
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

# Brand kit tokens (brand/tokens.json in the hub): surfaces, series and accent text per theme.
THEMES = {
    "light": {"panel": "#FFFFFF", "line": "#D5DAE0", "ink": "#111A24", "ink2": "#4A5866", "muted": "#6B7785",
              "valuation": "#4F46E5", "tps": "#0B3D91", "tps_text": "#2160B0", "warning": "#875D00"},
    "dark": {"panel": "#1A2430", "line": "#2E3B48", "ink": "#EEF1F4", "ink2": "#B6C0CA", "muted": "#8592A0",
             "valuation": "#7882E0", "tps": "#9DBDF2", "tps_text": "#9DBDF2", "warning": "#FAB219"},
}
SANS = "'Space Grotesk', -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'Space Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
W, H = 480, 260


def load(source: str, name: str) -> dict:
    if source.startswith("http"):
        req = urllib.request.Request(source + name, headers={"User-Agent": "profile-previews"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    return json.loads((Path(source) / name).read_text(encoding="utf-8"))


def pct(x: float) -> str:
    return f"{math.floor(x * 100 + 0.5)}%"   # rounds half up, like the apps


def cents(x: float) -> str:
    return f"${x:,.2f}"


def day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}, {d.year}"


def text(x, y, s, *, size=14, fill, family=SANS, weight=400, anchor="start", spacing=None) -> str:
    extra = f' letter-spacing="{spacing}"' if spacing else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{escape(s)}</text>')


def card(t: dict, label: str, title: str, body: list[str], cap: str) -> str:
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(label)}">',
        f"<title>{escape(label)}</title>",
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="22" fill="{t["panel"]}" stroke="{t["line"]}"/>',
        f'<clipPath id="card"><rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="22"/></clipPath>',
        f'<rect x="0" y="0" width="{W}" height="5" fill="{cap}" clip-path="url(#card)"/>',
        text(24, 38, title.upper(), size=11.5, fill=t["ink2"], weight=600, spacing="1.2"),
        *body,
        "</svg>", ""])


def valuation_svg(t: dict, company: dict, run: dict, cmp: dict) -> str:
    blend = cmp["blend"]
    p10, p50, p90 = blend["p10"], blend["p50"], blend["p90"]
    price = cmp.get("price") if isinstance(cmp.get("price"), (int, float)) else None
    lo = math.floor(min(p10, price or p10) / 25) * 25
    hi = math.ceil(max(p90, price or p90) / 25) * 25
    x0, x1 = 24, W - 24
    x = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    c = t["valuation"]
    rng = f"{cents(p10)}–{cents(p90)}"
    body = [
        text(24, 84, rng, size=34, fill=c, family=MONO, weight=700),
        text(24, 110, "a share, middle 80% of simulated outcomes", size=15, fill=t["ink"]),
        # one bar: the middle 80% of runs, with the median marked
        f'<rect x="{x0}" y="146" width="{x1 - x0}" height="14" rx="7" fill="{t["line"]}" opacity="0.6"/>',
        f'<rect x="{x(p10):.1f}" y="146" width="{x(p90) - x(p10):.1f}" height="14" rx="7" fill="{c}" opacity="0.85"/>',
        f'<rect x="{x(p50) - 1.5:.1f}" y="140" width="3" height="26" rx="1.5" fill="{t["ink"]}"/>',
        text(x(p50), 184, f"median {cents(p50)}", size=12, fill=t["ink2"], family=MONO, anchor="middle"),
        text(x0, 184, f"${lo:,}", size=12, fill=t["muted"], family=MONO),
        text(x1, 184, f"${hi:,}", size=12, fill=t["muted"], family=MONO, anchor="end"),
    ]
    if price:
        body.append(f'<rect x="{x(price) - 1:.1f}" y="136" width="2" height="34" fill="{t["warning"]}"/>')
    body += [
        text(24, 220, f"{company['name']} from SEC filings, as of {day(run['as_of'])}", size=12.5, fill=t["ink2"]),
        text(24, 240, "Open the Valuation Model →", size=13, fill=c, weight=600),
    ]
    label = (f"Valuation Model: {company['name']} is worth {rng} a share, the middle 80% of simulated outcomes, "
             f"median {cents(p50)}. From SEC filings as of {day(run['as_of'])}.")
    return card(t, label, f"Valuation Model · {company['name']}", body, c), label


def tps_svg(t: dict, p: dict) -> str:
    share = p["kpis"]["weeks_meeting_every_requirement"]
    days = [next(d for d in p["days"] if d["day"] == name) for name in DAYS]
    lo = max(0, min(min(d["available_p10"], d["needed"]) for d in days) - 1)
    hi = max(max(d["available_p90"], d["needed"]) for d in days) + 1
    top, bottom = 126, 200
    y = lambda v: bottom - (v - lo) / (hi - lo) * (bottom - top)
    c = t["tps"]
    left, right = 250, W - 28
    step = (right - left) / len(days)
    body = [
        text(24, 92, pct(share), size=52, fill=t["tps_text"], family=MONO, weight=700),
        text(24, 120, "of simulated weeks meet", size=15, fill=t["ink"]),
        text(24, 140, "every requirement", size=15, fill=t["ink"]),
        text(24, 168, f"{p['unit_name']}, {p['scenario_label'].lower()}", size=12.5, fill=t["ink2"]),
        text(24, 186, f"{p['simulation']['runs']:,} seeded runs, synthetic inputs", size=12.5, fill=t["ink2"]),
        text(left, 80, "Aircraft ready vs needed", size=12, fill=t["ink2"], weight=600),
        text(left, 98, "bar: middle 80% · dash: needed", size=11, fill=t["muted"]),
    ]
    for i, d in enumerate(days):
        cx = left + step * (i + 0.5)
        flag = d["status"] != "good"
        a, b = y(d["available_p90"]), y(d["available_p10"])
        if b - a < 8:
            a, b = (a + b) / 2 - 5, (a + b) / 2 + 5
        body += [
            f'<rect x="{cx - 9:.1f}" y="{a:.1f}" width="18" height="{b - a:.1f}" rx="6" fill="{c}" opacity="0.8"/>',
            f'<rect x="{cx - 11:.1f}" y="{y(d["available_p50"]) - 1.25:.1f}" width="22" height="2.5" rx="1" fill="{t["ink"]}"/>',
            f'<line x1="{cx - step / 2 + 4:.1f}" x2="{cx + step / 2 - 4:.1f}" y1="{y(d["needed"]):.1f}" y2="{y(d["needed"]):.1f}" '
            f'stroke="{t["warning"] if flag else t["ink2"]}" stroke-width="2.5" stroke-dasharray="5 3"/>',
            text(cx, bottom + 18, d["day"], size=12, fill=t["warning"] if flag else t["ink2"], anchor="middle",
                 weight=600 if flag else 400),
        ]
    body += [
        text(24, 240, "Open Turn Pattern Sustainability →", size=13, fill=t["tps_text"], weight=600),
    ]
    said = "; ".join(f"{d['day']} {d['available_p10']:g} to {d['available_p90']:g} ready, {d['needed']} needed" for d in days)
    label = (f"Turn Pattern Sustainability: {pct(share)} of simulated weeks meet every requirement "
             f"({p['unit_name']}, {p['scenario_label'].lower()}, {p['simulation']['runs']:,} runs). {said}.")
    return card(t, label, "Turn Pattern Sustainability", body, c), label


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--valuation-data", default=SITE + "valuation/data/")
    ap.add_argument("--tps-data", default=SITE + "TPS-Monte-Carlo-Simulation/data/")
    args = ap.parse_args()
    vsrc, tsrc = (s if s.startswith("http") else s.rstrip("/") + "/" for s in (args.valuation_data, args.tps_data))

    index = load(vsrc, "index.json")
    company = next((c for c in index["companies"] if c["ticker"] == VAL_TICKER), index["companies"][0])
    run = company["runs"][0]
    cmp = load(vsrc, run["comparison"])
    presets = load(tsrc, "presets.json")
    preset = load(tsrc, f"preset_{presets['default']}.json")

    OUT.mkdir(exist_ok=True)
    alts = {}
    for theme, t in THEMES.items():
        for key, (svg, label) in (("valuation", valuation_svg(t, company, run, cmp)), ("tps", tps_svg(t, preset))):
            (OUT / f"{key}-{theme}.svg").write_text(svg, encoding="utf-8")
            alts[key] = label
    # Keep the README's alt text in step with the picture, so a screen reader hears today's numbers.
    readme = ROOT / "README.md"
    md = readme.read_text(encoding="utf-8")
    for key, label in alts.items():
        md = re.sub(rf'(<img src="previews/{key}-light\.svg"[^>]*? alt=")[^"]*(")',
                    lambda m: m.group(1) + escape(label + " Opens the app.") + m.group(2), md)
    readme.write_text(md, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}/: {company['ticker']} {cents(cmp['blend']['p10'])}–{cents(cmp['blend']['p90'])}, "
          f"TPS {pct(preset['kpis']['weeks_meeting_every_requirement'])}")


if __name__ == "__main__":
    main()
