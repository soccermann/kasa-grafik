#!/usr/bin/env python3
"""Ön filtre: TradingView toplu sorgu sonuçlarından sıkışma + kıpırdanma adaylarını seçer.

Girdi: JSON dosyaları; her biri {"BINANCE:XUSDT": {...kolonlar...}, ...} biçiminde
(get_symbol_data_batch yanıtındaki "data" nesnesi; yalnızca change|60 veya change|240 >= 1
olan satırları yazmak yeterli).
Kolonlar: close, change, change|60, change|240, Perf.W, BB.upper|240, BB.lower|240, High.1M, Low.1M

Kullanım: python3 onfiltre.py dosya1.json [dosya2.json ...] [--limit 15]
Çıktı: adaylar (en güçlü kıpırdanma / en dar bant önce), satır başına bir sembol.
"""
import json
import sys


def puan(r):
    try:
        c = r["close"]
        u, l = r["BB.upper|240"], r["BB.lower|240"]
        h1m, l1m = r["High.1M"], r["Low.1M"]
        ch, pw = r["change"], r["Perf.W"]
        c60, c240 = r.get("change|60"), r.get("change|240")
    except KeyError:
        return None
    if None in (c, u, l, h1m, l1m, ch, pw) or c <= 0:
        return None
    akt = max(x for x in (c60, c240, -99) if x is not None)
    bbw = (u - l) / c
    poz = (c - l1m) / (h1m - l1m) if h1m > l1m else 0.5
    if akt < 1.0:            # son 1-4 saatte kıpırdanma yok
        return None
    if akt >= 10:            # sıçrama zaten oldu
        return None
    if bbw > 0.20:           # 4 saatlikte sıkışma yok
        return None
    if not (-8 <= ch <= 10):
        return None
    if pw > 20:
        return None
    if poz > 0.6:            # tabandan / dipten uzak
        return None
    return akt / max(bbw, 0.01)


def main():
    args = sys.argv[1:]
    limit = 15
    if "--limit" in args:
        i = args.index("--limit")
        limit = int(args[i + 1])
        del args[i:i + 2]
    adaylar = {}
    for yol in args:
        with open(yol) as f:
            veri = json.load(f)
        veri = veri.get("data", veri)
        for sembol, r in veri.items():
            if sembol in ("BINANCE:BTCUSDT", "BINANCE:ETHUSDT"):
                continue
            p = puan(r)
            if p is not None:
                adaylar[sembol] = p
    sirali = sorted(adaylar.items(), key=lambda kv: -kv[1])
    for s, p in sirali[:limit]:
        print(s)
    print(f"# {len(sirali)} aday, ilk {min(limit, len(sirali))} seçildi", file=sys.stderr)


if __name__ == "__main__":
    main()
