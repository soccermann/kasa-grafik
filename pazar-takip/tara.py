#!/usr/bin/env python3
"""Pazar taraması (BIST, umit liste).
Kullanım: python3 tara.py SCREENER.json umit_liste.txt TARIH(YYYY-MM-DD) CIKTI_DIR
  SCREENER.json : mcp-tv-run-screener çıktısı (market turkey, filters {"close":[0,null]}, limit 1000,
                  columns name, close, SMA50, SMA200, Perf.1M, Perf.3M, price_52_week_high, average_volume_10d_calc, RSI)
                  Araç çıktısı dosyaya kaydedildiyse o dosya doğrudan verilebilir.
Çıktı: CIKTI_DIR/TARIH.json (liste kaydı) ve CIKTI_DIR/mesaj_TARIH.txt (Telegram HTML mesajı). Özet stdout'a.
Kurallar (18 Ekim 2026 testi, 503 hisse, 2019-2026):
  genişlik = umit listede fiyatı SMA50 üstünde olan hisse oranı (SMA200 verisi olanlar arasında)
  genişlik >= %20 -> GÜÇ (A1): Perf.3M listenin en iyi %20'si, fiyat 52H yüksekten en fazla %15 aşağıda,
                     ciro (kapanış x 10g ort. hacim) listenin alt %40'ı; Perf.3M'e göre ilk 10; 1 hafta tut
  genişlik <  %20 -> TEPKİ (T1): Perf.1M -%60 ile -%20 arası, ciro alt %40 ve >= 10M TL;
                     en çok düşenden ilk 10; 2 hafta tut
"""
import json, sys, re
from datetime import date, timedelta

def load_rows(path):
    t = open(path).read()
    try:
        d = json.loads(t)
    except Exception:
        d = json.loads(json.loads(t)[0]['text'])
    if isinstance(d, list): d = json.loads(d[0]['text'])
    return d['data']['rows']

def pct(x):
    return ('+' if x >= 0 else '−') + '%' + trnum(abs(x), 1)

def trnum(x, nd=2):
    s = f"{x:,.{nd}f}"
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')

def main(scr, liste, tarih, out):
    umit = set(open(liste).read().split())
    rows = [r for r in load_rows(scr) if r.get('name') in umit and r.get('close')]
    for r in rows:
        r['ciro'] = (r.get('average_volume_10d_calc') or 0) * r['close']
    base = [r for r in rows if r.get('SMA200') and r.get('SMA50')]
    br = sum(r['close'] > r['SMA50'] for r in base) / max(len(base), 1)
    cir = sorted(r['ciro'] for r in rows)
    c40 = cir[int(len(cir) * .4)]
    if br >= .2:
        mod, tut = 'GUC', 1
        p3 = sorted(r['Perf.3M'] for r in rows if r.get('Perf.3M') is not None)
        p80 = p3[int(len(p3) * .8)]
        sec = [r for r in rows if r.get('Perf.3M') is not None and r['Perf.3M'] >= p80 and r.get('price_52_week_high')
               and r['close'] / r['price_52_week_high'] - 1 > -.15 and r['ciro'] < c40]
        sec = sorted(sec, key=lambda r: -r['Perf.3M'])[:10]
    else:
        mod, tut = 'TEPKI', 2
        sec = [r for r in rows if r.get('Perf.1M') is not None and -60 < r['Perf.1M'] <= -20 and 10e6 <= r['ciro'] < c40]
        sec = sorted(sec, key=lambda r: r['Perf.1M'])[:10]
    d = date.fromisoformat(tarih)
    giris = d + timedelta(days=(7 - d.weekday()) % 7 or 7)          # sonraki Pazartesi
    cikis = giris + timedelta(days=4 + 7 * (tut - 1))                # 1 veya 2 hafta sonraki Cuma
    kayit = dict(tarih=tarih, mod=mod, tutma_hafta=tut, giris_gunu=str(giris), cikis_gunu=str(cikis),
                 genislik=round(br * 100, 1), ciro_esik_tl=round(c40), taranan=len(rows),
                 hisseler=[dict(sembol=r['name'], pazar_kapanis=r['close'], perf_1m=round(r.get('Perf.1M') or 0, 1),
                                perf_3m=round(r.get('Perf.3M') or 0, 1), rsi=round(r.get('RSI') or 0),
                                ciro_m=round(r['ciro'] / 1e6, 1)) for r in sec])
    json.dump(kayit, open(f'{out}/{tarih}.json', 'w'), ensure_ascii=False, indent=1)
    g = d.strftime('%d.%m.%Y')
    if mod == 'GUC':
        bas = f"Mod: <b>GÜÇ</b> (genişlik %{trnum(br*100,1)})\nKural: son 3 ayın en güçlü %20'si + 52H zirveye %15'ten yakın + düşük ciro"
        satir = lambda i, h: f"{i}) <b>{h['sembol']}</b> – {trnum(h['pazar_kapanis'])} TL · 3A {pct(h['perf_3m'])}"
    else:
        bas = f"Mod: <b>TEPKİ</b> (genişlik %{trnum(br*100,1)}, piyasa çok zayıf)\nKural: son 1 ayda %20–60 düşen, düşük cirolu hisseler"
        satir = lambda i, h: f"{i}) <b>{h['sembol']}</b> – {trnum(h['pazar_kapanis'])} TL · 1A {pct(h['perf_1m'])} · RSI {h['rsi']}"
    m = [f"📅 <b>HAFTALIK TARAMA – {g}</b>", bas,
         f"Takip: {giris.strftime('%d.%m')} Pazartesi açılış → {cikis.strftime('%d.%m')} Cuma kapanış ({tut} hafta)", ""]
    if sec:
        m += [satir(i + 1, h) for i, h in enumerate(kayit['hisseler'])]
    else:
        m.append("Bu hafta kurallara uyan hisse çıkmadı.")
    m += ["", "📊 Performans her Cuma kapanıştan sonra paylaşılacak.",
          "ℹ️ Deneme amaçlı takip listesidir, yatırım tavsiyesi değildir."]
    open(f'{out}/mesaj_{tarih}.txt', 'w').write('\n'.join(m))
    print(json.dumps({k: v for k, v in kayit.items() if k != 'hisseler'}, ensure_ascii=False),
          [h['sembol'] for h in kayit['hisseler']])

if __name__ == '__main__':
    main(*sys.argv[1:5])
