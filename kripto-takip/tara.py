#!/usr/bin/env python3
"""Sıkışma + hacim kıvılcımı taraması (1 saatlik mumlar).

Her aday için get_ohlcv (interval 1h, count 72, format columns) yanıtındaki "bars"
nesnesi bars/<SEMBOL>.json olarak kaydedilir (SEMBOL = BINANCE:XUSDT -> XUSDT.json).

Kullanım: python3 tara.py <bars_klasoru> <sinyaller.csv> <mesaj_cikti.txt> [taranan_sayisi]
- Koşulları sağlayanları sinyaller.csv'ye ekler (aynı coin son 48 saatte sinyal verdiyse atlar).
- Telegram'a gidecek HTML mesajı mesaj_cikti.txt'ye yazar (yeni sinyal yoksa dosya boş olur).

Kriterler (17 Eki 2026 analizinden):
- Kıvılcım: son 8 tamamlanmış mumdan birinde hacim >= önceki 48 mumun ortanca hacminin 3 katı
  ve o mumun gövdesi -%3 ile +%9 arasında
- Taban: kıvılcımdan önceki 24 mumun (en yüksek - en düşük) / en düşük <= %12
- Fiyat tabanın üst sınırının en fazla %8 üstünde (henüz kaçmamış)
- Son 24 mumda %10+ mum yok (sıçrama henüz olmamış)
- Likidite: son 48 mumun ortanca saatlik işlem tutarı >= 15.000 USDT
"""
import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone, timedelta

TR = timezone(timedelta(hours=3))
ALANLAR = ["sinyal_utc", "sembol", "fiyat", "taban_alt", "taban_ust", "taban_genislik_pct",
           "kivilcim_kat", "kivilcim_utc", "kivilcim_govde_pct"]


def tr_sayi(x, ondalik=None):
    if ondalik is None:
        import math
        ondalik = 2 if x >= 1 else min(10, 3 - int(math.floor(math.log10(abs(x)))))  # ~4 anlamlı basamak
    s = f"{x:,.{ondalik}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def degerlendir(b, simdi):
    t, o, h, l, c, v = b["t"], b["o"], b["h"], b["l"], b["c"], b["v"]
    canli = c[-1]   # oluşmakta olan mum dahil son fiyat
    n = len(t)
    # yalnızca tamamlanmış mumlar
    while n and t[n - 1] + 3600 > simdi:
        n -= 1
    if n < 60:
        return None
    t, o, h, l, c, v = (list(x[:n]) for x in (t, o, h, l, c, v))
    if any((c[i] - o[i]) / o[i] >= 0.10 for i in range(n - 24, n)):
        return None
    tutar = [v[i] * c[i] for i in range(n - 48, n)]
    if statistics.median(tutar) < 15000:
        return None
    ref = statistics.median(v[-56:-8])
    if ref <= 0:
        return None
    en_iyi = None
    for i in range(n - 8, n):
        kat = v[i] / ref
        govde = (c[i] - o[i]) / o[i]
        if not (kat >= 3 and -0.03 <= govde <= 0.09):
            continue
        # Taban: kıvılcımdan önceki 24 mum (kıvılcımın kendi fitili tabanı bozmasın)
        taban_h, taban_l = max(h[i - 24:i]), min(l[i - 24:i])
        genislik = (taban_h - taban_l) / taban_l
        if genislik > 0.12:
            continue
        if canli > taban_h * 1.08:   # fiyat tabandan çoktan kaçmış
            continue
        if en_iyi is None or kat > en_iyi[0]:
            en_iyi = (kat, i, govde, taban_h, taban_l, genislik)
    if en_iyi is None:
        return None
    kat, i, govde, taban_h, taban_l, genislik = en_iyi
    return {
        "fiyat": canli, "taban_alt": taban_l, "taban_ust": taban_h,
        "taban_genislik_pct": round(genislik * 100, 1), "kivilcim_kat": round(kat, 1),
        "kivilcim_utc": datetime.fromtimestamp(t[i], timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "kivilcim_govde_pct": round(govde * 100, 1),
    }


def main():
    klasor, csv_yol, mesaj_yol = sys.argv[1:4]
    taranan = sys.argv[4] if len(sys.argv) > 4 else "?"
    simdi = time.time()
    simdi_dt = datetime.fromtimestamp(simdi, timezone.utc)

    onceki = []
    if os.path.exists(csv_yol):
        with open(csv_yol, newline="") as f:
            onceki = list(csv.DictReader(f))
    yakin = {r["sembol"] for r in onceki
             if simdi_dt - datetime.fromisoformat(r["sinyal_utc"].replace("Z", "+00:00")) < timedelta(hours=48)}

    yeni = []
    for ad in sorted(os.listdir(klasor)):
        if not ad.endswith(".json"):
            continue
        sembol = ad[:-5]
        with open(os.path.join(klasor, ad)) as f:
            veri = json.load(f)
        bars = veri.get("bars", veri)
        s = degerlendir(bars, simdi)
        if s is None:
            continue
        if sembol in yakin:
            print(f"{sembol}: koşul sağlandı ama son 48 saatte zaten bildirildi, atlandı")
            continue
        s["sembol"] = sembol
        s["sinyal_utc"] = simdi_dt.strftime("%Y-%m-%dT%H:%MZ")
        yeni.append(s)

    yeni.sort(key=lambda r: -r["kivilcim_kat"])
    yaz_baslik = not os.path.exists(csv_yol)
    with open(csv_yol, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ALANLAR)
        if yaz_baslik:
            w.writeheader()
        for r in yeni:
            w.writerow({k: r[k] for k in ALANLAR})

    if not yeni:
        open(mesaj_yol, "w").close()
        print("Yeni sinyal yok.")
        return

    zaman = simdi_dt.astimezone(TR).strftime("%d.%m.%Y %H:%M")
    satirlar = [f"🔎 <b>KRİPTO – SIKIŞMA + HACİM KIVILCIMI</b>",
                f"{zaman} · Binance · 1 saatlik mumlar · {taranan} parite tarandı", ""]
    for k, r in enumerate(yeni, 1):
        kiv = datetime.fromisoformat(r["kivilcim_utc"].replace("Z", "+00:00")).astimezone(TR).strftime("%H:%M")
        ad = r["sembol"].replace("USDT", "/USDT")
        satirlar.append(f"<b>{k}) {ad}</b> – Fiyat {tr_sayi(r['fiyat'])}")
        satirlar.append(f"Taban {tr_sayi(r['taban_alt'])}–{tr_sayi(r['taban_ust'])} "
                        f"(%{tr_sayi(r['taban_genislik_pct'], 1)}) · Kıvılcım {tr_sayi(r['kivilcim_kat'], 1)}x hacim ({kiv})")
        satirlar.append(f"Geçersiz: {tr_sayi(r['taban_alt'])} altı kapanış")
        satirlar.append("")
    satirlar.append("📅 Sonuçlar 7 gün sonra takip edilip paylaşılacak.")
    satirlar.append("ℹ️ Teknik tarama çalışmasıdır, yatırım tavsiyesi değildir.")
    with open(mesaj_yol, "w") as f:
        f.write("\n".join(satirlar))
    print(f"{len(yeni)} yeni sinyal: " + ", ".join(r["sembol"] for r in yeni))


if __name__ == "__main__":
    main()
