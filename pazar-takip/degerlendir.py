#!/usr/bin/env python3
"""Pazar taraması performans takibi.
Kullanım: python3 degerlendir.py BUGUN(YYYY-MM-DD) BARS_DIR MESAJ_CIKTI
  listeler/*.json  : tara.py'nin kaydettiği haftalık listeler (bu klasörün içinde)
  BARS_DIR         : her sembol için SEMBOL.json = mcp-tv-get-ohlcv (interval 1D, format columns) yanıtındaki
                     "bars" nesnesi {t:[unix sn], o:[], h:[], l:[], c:[], v:[]}; ayrıca XU100.json (BIST:XU100)
Hangi listeler değerlendirilir: giris_gunu <= BUGUN ve henüz "kapandi" olmayanlar.
  Giriş fiyatı = giris_gunu açılışı; güncel = BUGUN'e kadarki son kapanış (en geç cikis_gunu).
  BUGUN >= cikis_gunu ise liste KAPANIR: sonuclar.csv'ye satırlar eklenir ve listedeki "kapandi": true yapılır.
Çıktı: MESAJ_CIKTI (Telegram HTML). Ayrıca gerekli bar dosyalarının listesini görmek için: python3 degerlendir.py --semboller BUGUN
"""
import json, sys, glob, os, csv
from datetime import date, datetime, timezone, timedelta
HERE = os.path.dirname(os.path.abspath(__file__))
TR = timezone(timedelta(hours=3))

def trn(x, nd=2):
    return f"{x:,.{nd}f}".replace(',', 'X').replace('.', ',').replace('X', '.')
def pct(x): return ('+' if x >= 0 else '−') + '%' + trn(abs(x), 1)

def acik_listeler(bugun):
    out = []
    for f in sorted(glob.glob(f'{HERE}/listeler/*.json')):
        L = json.load(open(f))
        if L.get('kapandi') or L['giris_gunu'] > bugun: continue
        out.append((f, L))
    return out

def bars(dir_, sym):
    p = f'{dir_}/{sym}.json'
    if not os.path.exists(p): return None
    b = json.load(open(p)); b = b.get('bars', b)
    d = [datetime.fromtimestamp(t, TR).date().isoformat() for t in b['t']]
    return dict(d=d, o=b['o'], c=b['c'])

def perf(b, g, cik, bugun):
    if b is None: return None
    i = next((k for k, x in enumerate(b['d']) if x >= g), None)
    if i is None or b['d'][i] > cik: return None
    son = max(k for k, x in enumerate(b['d']) if x <= min(cik, bugun))
    if son < i: return None
    return dict(giris=b['o'][i], giris_gun=b['d'][i], son=b['c'][son], son_gun=b['d'][son], r=(b['c'][son] / b['o'][i] - 1) * 100)

def main(bugun, bdir, outp):
    msgs = []
    for f, L in acik_listeler(bugun):
        kapan = bugun >= L['cikis_gunu']
        xu = perf(bars(bdir, 'XU100'), L['giris_gunu'], L['cikis_gunu'], bugun)
        rows = []
        for h in L['hisseler']:
            p = perf(bars(bdir, h['sembol']), L['giris_gunu'], L['cikis_gunu'], bugun)
            rows.append((h['sembol'], p))
        ok = [p['r'] for s, p in rows if p]
        ort = sum(ok) / len(ok) if ok else None
        bas = 'SONUÇ' if kapan else 'ARA DURUM'
        tl = datetime.fromisoformat(L['tarih']).strftime('%d.%m.%Y')
        m = [f"📊 <b>HAFTALIK TARAMA {bas} – {tl} listesi</b>",
             f"Mod: {'GÜÇ' if L['mod']=='GUC' else 'TEPKİ'} · {datetime.fromisoformat(L['giris_gunu']).strftime('%d.%m')} açılış → "
             f"{datetime.fromisoformat(min(L['cikis_gunu'], bugun)).strftime('%d.%m')} kapanış" + ('' if kapan else f" (takip {datetime.fromisoformat(L['cikis_gunu']).strftime('%d.%m')}'de bitiyor)"), ""]
        for i, (s, p) in enumerate(sorted(rows, key=lambda x: -(x[1]['r'] if x[1] else -1e9)), 1):
            m.append(f"{'🟢' if p and p['r']>0 else '🔴' if p else '⚪'} <b>{s}</b> " + (f"{trn(p['giris'])} → {trn(p['son'])} · {pct(p['r'])}" if p else "veri yok"))
        m.append("")
        if ort is not None:
            kaz = sum(r > 0 for r in ok)
            m.append(f"Ortalama: <b>{pct(ort)}</b> · Kazanan: {kaz}/{len(ok)}")
        if xu: m.append(f"BIST 100 aynı dönemde: {pct(xu['r'])}" + (f" · Fark: <b>{pct(ort - xu['r'])}</b>" if ort is not None else ''))
        if kapan:
            L['kapandi'] = True; json.dump(L, open(f, 'w'), ensure_ascii=False, indent=1)
            sp = f'{HERE}/sonuclar.csv'; yeni = not os.path.exists(sp)
            with open(sp, 'a', newline='') as fh:
                w = csv.writer(fh)
                if yeni: w.writerow(['liste_tarihi', 'mod', 'sembol', 'giris_gun', 'giris', 'cikis_gun', 'cikis', 'getiri_yuzde', 'xu100_yuzde'])
                for s, p in rows:
                    if p: w.writerow([L['tarih'], L['mod'], s, p['giris_gun'], p['giris'], p['son_gun'], p['son'], round(p['r'], 2), round(xu['r'], 2) if xu else ''])
            # kümülatif
            R = list(csv.DictReader(open(sp)))
            by = {}
            for r in R: by.setdefault(r['liste_tarihi'], []).append(r)
            lo = [sum(float(x['getiri_yuzde']) for x in v) / len(v) for v in by.values()]
            lx = [float(v[0]['xu100_yuzde']) for v in by.values() if v[0]['xu100_yuzde'] != '']
            m.append(f"Kümülatif ({len(lo)} liste): ortalama liste getirisi {pct(sum(lo)/len(lo))}" + (f", BIST 100 ort. {pct(sum(lx)/len(lx))}" if lx else '')
                     + f", piyasayı geçen liste {sum(1 for a,b in zip(lo,lx) if a>b)}/{len(lx)}")
        m.append("ℹ️ Deneme takibi, yatırım tavsiyesi değildir.")
        msgs.append('\n'.join(m))
    open(outp, 'w').write('\n\n———\n\n'.join(msgs))
    print(len(msgs), 'liste değerlendirildi')

if __name__ == '__main__':
    if sys.argv[1] == '--semboller':
        s = {'XU100'}
        for f, L in acik_listeler(sys.argv[2]): s |= {h['sembol'] for h in L['hisseler']}
        print(' '.join(sorted(s)))
    else:
        main(*sys.argv[1:4])
