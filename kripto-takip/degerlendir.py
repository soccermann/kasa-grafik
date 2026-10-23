#!/usr/bin/env python3
"""Haftalık sonuç raporu: sinyallerden sonra coinler sıçradı mı?

Her sinyal verilen coin için get_ohlcv (interval 1h, count 200, format columns) yanıtının
"bars" nesnesi bars/<SEMBOL>.json olarak kaydedilir.

Kullanım: python3 degerlendir.py <sinyaller.csv> <bars_klasoru> <mesaj_cikti.txt> <sonuclar.csv>

Her sinyal için sinyal anından itibaren (en fazla 168 saat):
- en yüksek yükseliş % (en yüksek fiyat / sinyal fiyatı - 1)
- en derin düşüş %   (en düşük fiyat / sinyal fiyatı - 1)
- şu anki değişim %
- tabanın altına kapanış oldu mu (geçersiz)
- "sıçradı" = en yüksek yükseliş >= %10
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone, timedelta

TR = timezone(timedelta(hours=3))


def pct(x):
    return f"{x:+.1f}".replace(".", ",")


def main():
    csv_yol, klasor, mesaj_yol, sonuc_yol = sys.argv[1:5]
    with open(csv_yol, newline="") as f:
        sinyaller = list(csv.DictReader(f))
    sonuclar = []
    for s in sinyaller:
        yol = os.path.join(klasor, s["sembol"] + ".json")
        if not os.path.exists(yol):
            continue
        with open(yol) as f:
            b = json.load(f)
        b = b.get("bars", b)
        t0 = datetime.fromisoformat(s["sinyal_utc"].replace("Z", "+00:00")).timestamp()
        idx = [i for i, t in enumerate(b["t"]) if t0 <= t < t0 + 168 * 3600]
        if not idx:
            continue
        p0 = float(s["fiyat"])
        taban = float(s["taban_alt"])
        yuksek = max(b["h"][i] for i in idx) / p0 - 1
        dusuk = min(b["l"][i] for i in idx) / p0 - 1
        simdi = b["c"][idx[-1]] / p0 - 1
        gecersiz = any(b["c"][i] < taban for i in idx)
        saat = len(idx)
        sonuclar.append({**s, "saat": saat, "en_yuksek_pct": round(yuksek * 100, 1),
                         "en_dusuk_pct": round(dusuk * 100, 1), "simdi_pct": round(simdi * 100, 1),
                         "gecersiz": "evet" if gecersiz else "hayır",
                         "sicradi": "evet" if yuksek >= 0.10 else "hayır"})

    if sonuclar:
        with open(sonuc_yol, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(sonuclar[0].keys()))
            w.writeheader()
            w.writerows(sonuclar)

    n = len(sonuclar)
    sicrayan = sum(r["sicradi"] == "evet" for r in sonuclar)
    satirlar = ["📊 <b>KRİPTO TAKİP – 1 HAFTALIK SONUÇ</b>",
                f"Sıkışma + hacim kıvılcımı sinyalleri · {datetime.now(TR).strftime('%d.%m.%Y')}", ""]
    if n == 0:
        satirlar.append("Bu hafta değerlendirilecek sinyal yok.")
    else:
        ort_y = sum(r["en_yuksek_pct"] for r in sonuclar) / n
        ort_s = sum(r["simdi_pct"] for r in sonuclar) / n
        satirlar.append(f"<b>{n} sinyalden {sicrayan} tanesi %10+ sıçradı</b> (isabet %{round(100 * sicrayan / n)})")
        satirlar.append(f"Ortalama en yüksek yükseliş %{pct(ort_y)} · ortalama şu anki değişim %{pct(ort_s)}")
        satirlar.append("")
        for r in sorted(sonuclar, key=lambda r: -r["en_yuksek_pct"]):
            isaret = "✅" if r["sicradi"] == "evet" else ("❌" if r["gecersiz"] == "evet" else "➖")
            tarih = datetime.fromisoformat(r["sinyal_utc"].replace("Z", "+00:00")).astimezone(TR).strftime("%d.%m %H:%M")
            satirlar.append(f"{isaret} <b>{r['sembol'].replace('USDT', '')}</b> ({tarih}) – en yüksek %{pct(r['en_yuksek_pct'])}, "
                            f"şu an %{pct(r['simdi_pct'])}, en dip %{pct(r['en_dusuk_pct'])}"
                            + (f" · {r['saat']} saatlik veri" if r["saat"] < 168 else ""))
        satirlar.append("")
        satirlar.append("✅ %10+ sıçradı · ❌ tabanın altına kapandı · ➖ ikisi de değil")
    satirlar.append("ℹ️ Teknik tarama çalışmasıdır, yatırım tavsiyesi değildir.")
    with open(mesaj_yol, "w") as f:
        f.write("\n".join(satirlar))
    print("\n".join(satirlar))


if __name__ == "__main__":
    main()
