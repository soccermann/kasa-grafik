"""Kasa listesi grafik cizici.

Kullanim:  python3 ciz.py BARLAR.json SPEC.json CIKTI.png

BARLAR.json : TradingView get_ohlcv 'columns' formatindaki bars nesnesi
              {"t":[...], "o":[...], "h":[...], "l":[...], "c":[...]}
SPEC.json   : cizim tarifi (ornek: tools/ornek_spec.json)
  symbol, tf (orn "1 saat"), title, subtitle, date (orn "16.10.2026"),
  ylim [alt, ust] (opsiyonel), info (cok satirli metin), info_loc tl|tr|bl|br,
  zones  : [{x0, x1, lo, hi, color}]
  lines  : [{y, x0, x1, color, label, style: solid|dashed|dotted}]
  arrows : [{x, y, label, color, dx, dy}]
  path   : [{xs:[...], ys:[...], color}]
x degerleri bar indeksidir; negatif deger sondan sayilir (-1 = son bar).
Renkler: up, down, blue, orange, purple, gray, green
"""
import json, sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "DejaVu Sans"
COL = dict(up="#089981", down="#F23645", blue="#2962ff", orange="#ff9800",
           purple="#9c27b0", gray="#787b86", green="#2e7d32")
LS = dict(solid="-", dashed="--", dotted=":")


def main(bars_path, spec_path, out_path):
    b = json.load(open(bars_path))
    if "bars" in b:
        b = b["bars"]
    df = pd.DataFrame({k: b[k] for k in "tohlc"})
    df["dt"] = pd.to_datetime(df.t, unit="s") + pd.Timedelta(hours=3)
    s = json.load(open(spec_path))
    n = len(df)
    X = lambda x: n + x if x < 0 else x
    c = lambda k: COL.get(k, k)

    lo_all, hi_all = df.l.min(), df.h.max()
    ys = [z["lo"] for z in s.get("zones", [])] + [z["hi"] for z in s.get("zones", [])] + [l["y"] for l in s.get("lines", [])]
    if ys:
        lo_all, hi_all = min(lo_all, min(ys)), max(hi_all, max(ys))
    pad = (hi_all - lo_all) * 0.08
    ylim = s.get("ylim") or [lo_all - pad, hi_all + pad]

    f, ax = plt.subplots(figsize=(13, 7))
    for i, r in df.iterrows():
        col = COL["up"] if r.c >= r.o else COL["down"]
        ax.vlines(i, r.l, r.h, color=col, lw=0.9, zorder=2)
        ax.add_patch(plt.Rectangle((i - 0.35, min(r.o, r.c)), 0.7,
                     max(abs(r.c - r.o), (ylim[1] - ylim[0]) * 0.002), color=col, zorder=3))
    days = df.dt.dt.date
    starts = list(df.index[days.ne(days.shift())])
    for i in starts[1:]:
        ax.axvline(i - 0.5, color="#e0e3eb", lw=0.8, ls="--", zorder=1)
    step = max(1, len(starts) // 12)
    ticks = starts[::step]
    ax.set_xticks(ticks)
    ax.set_xticklabels([df.dt[i].strftime("%d.%m") for i in ticks], fontsize=9)
    ax.set_xlim(-1, n + 14)
    ax.set_ylim(*ylim)
    ax.grid(alpha=0.25)
    ax.yaxis.tick_right()
    for sp in ("top", "left"):
        ax.spines[sp].set_visible(False)

    for z in s.get("zones", []):
        ax.add_patch(plt.Rectangle((X(z["x0"]), z["lo"]), X(z["x1"]) - X(z["x0"]), z["hi"] - z["lo"],
                     color=c(z.get("color", "blue")), alpha=z.get("alpha", 0.12), lw=0, zorder=1))
    for l in s.get("lines", []):
        x0, x1 = X(l.get("x0", 0)), X(l.get("x1", -1)) + 2
        ax.plot([x0, x1], [l["y"], l["y"]], color=c(l["color"]), ls=LS.get(l.get("style", "solid")), lw=1.6, zorder=4)
        if l.get("label"):
            ax.text(x1 + 0.5, l["y"], f" {l['label']} ", color="white", fontsize=8.5, va="center", ha="left",
                    bbox=dict(boxstyle="round,pad=0.2", fc=c(l["color"]), ec="none"), zorder=6)
    for p in s.get("path", []):
        ax.plot([X(x) for x in p["xs"]], p["ys"], color=c(p.get("color", "gray")), lw=1, ls=":")
    for a in s.get("arrows", []):
        ax.annotate(a["label"], (X(a["x"]), a["y"]), xytext=(a.get("dx", -80), a.get("dy", 35)),
                    textcoords="offset points", fontsize=9, color="white", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.3", fc=c(a.get("color", "blue")), ec="none"),
                    arrowprops=dict(arrowstyle="->", color=c(a.get("color", "blue")), lw=1.5), zorder=8)

    f.suptitle(s["title"], x=0.02, ha="left", fontsize=15, fontweight="bold", y=0.99)
    ax.set_title(s.get("subtitle", ""), loc="left", fontsize=10, color="#434651")
    if s.get("info"):
        x, y, ha, va = {"tl": (0.01, 0.97, "left", "top"), "bl": (0.01, 0.03, "left", "bottom"),
                        "tr": (0.80, 0.97, "right", "top"), "br": (0.80, 0.06, "right", "bottom")}[s.get("info_loc", "tl")]
        ax.text(x, y, s["info"], transform=ax.transAxes, ha=ha, va=va, fontsize=10, linespacing=1.55,
                bbox=dict(boxstyle="round,pad=0.6", fc="white", ec="#d1d4dc"), zorder=9)
    ax.text(0.995, 0.01, f"BIST:{s['symbol']} · {s.get('tf', '')} · Veri: TradingView · {s.get('date', '')}",
            transform=ax.transAxes, ha="right", fontsize=8, color=COL["gray"])
    f.savefig(out_path, dpi=100, bbox_inches="tight", facecolor="white")


if __name__ == "__main__":
    main(*sys.argv[1:4])
