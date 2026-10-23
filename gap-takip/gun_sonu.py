"""Gap-aşağı açılış kağıt takibi (09:55 açılıştan al, +%2'de sat, olmazsa kapanışta sat).

Kullanım:
  python3 gun_sonu.py SCREENER.json BUGUN [--haric SYM1,SYM2] [--mesaj CIKTI.txt]
SCREENER.json: TradingView mcp-tv-run-screener yanıtı (market turkey), kolonlar en az:
  name, open, close, high, low, gap, average_volume_10d_calc. Araç yanıtı dosyaya kaydettiyse o dosya
  doğrudan verilebilir ([{type,text}] biçimi de okunur).
--haric: o gün temettü/bedelsiz vb. nedeniyle fiyatı düzeltilen (sahte gap) hisseler; listeden çıkarılır.
Kurallar (5 yıllık DataStore testinden):
  aday   : -9,5 < açılış gapı <= -3  ve  10 günlük ort. işlem hacmi (adet x kapanış) >= 20 milyon TL
  işlem  : açılış fiyatından al; gün içi yüksek >= açılış x 1,02 ise +%2 sat, değilse kapanıştan sat; maliyet %0,2
Sonuç islemler.csv'ye eklenir (aynı tarih varsa tekrar eklenmez), Telegram mesajı yazılır.
"""
import sys, json, csv, os
from datetime import date

KOL = ['tarih', 'sembol', 'gap', 'acilis', 'yuksek', 'dusuk', 'kapanis', 'ciro_m', 'hedef', 'getiri']
MIN_CIRO = 20e6; MALIYET = 0.2; HEDEF = 2.0
BURADA = os.path.dirname(os.path.abspath(__file__)); CSV = os.path.join(BURADA, 'islemler.csv')

def oku(yol):
    d = json.load(open(yol))
    if isinstance(d, list):  # [{type,text}]
        d = json.loads(''.join(x.get('text', '') for x in d))
    if 'data' in d: d = d['data']
    return d['rows']

def tr(x, n=2):
    s = f"{x:,.{n}f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return s

def pct(x):
    return ('+' if x >= 0 else '−') + '%' + tr(abs(x))

def main():
    a = sys.argv[1:]
    scr, bugun = a[0], a[1]
    haric = set(); mesaj = os.path.join(BURADA, f'mesaj_{bugun}.txt')
    if '--haric' in a: haric = set(s.strip().upper() for s in a[a.index('--haric') + 1].split(',') if s.strip())
    if '--mesaj' in a: mesaj = a[a.index('--mesaj') + 1]
    rows = oku(scr)
    yeni = []
    for r in rows:
        try:
            s = r['name']; o, h, l, c, g, av = (float(r[k]) for k in ('open', 'high', 'low', 'close', 'gap', 'average_volume_10d_calc'))
        except (KeyError, TypeError, ValueError):
            continue
        if s.upper() in haric or o <= 0: continue
        ciro = av * c
        if not (-9.5 < g <= -3) or ciro < MIN_CIRO: continue
        hit = h >= o * (1 + HEDEF / 100) - 1e-9
        get = (HEDEF if hit else (c / o - 1) * 100) - MALIYET
        yeni.append(dict(tarih=bugun, sembol=s, gap=round(g, 2), acilis=o, yuksek=h, dusuk=l, kapanis=c,
                         ciro_m=round(ciro / 1e6, 1), hedef=int(hit), getiri=round(get, 2)))
    yeni.sort(key=lambda x: x['gap'])
    eski = list(csv.DictReader(open(CSV))) if os.path.exists(CSV) else []
    if any(e['tarih'] == bugun for e in eski):
        print('Bu tarih zaten kayıtlı; csv değişmedi.'); kayit = eski
    else:
        kayit = eski + [{k: str(v) for k, v in x.items()} for x in yeni]
        with open(CSV, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=KOL); w.writeheader(); w.writerows(kayit)
    # --- mesaj ---
    gg = date.fromisoformat(bugun).strftime('%d.%m.%Y')
    L = [f"📉➡️📈 <b>GAP-AŞAĞI TAKİBİ – {gg}</b>",
         "Kural: 09:55 açılışı −%3 ile −%9,5 arası gapla olan likit hisse (10g ort. ≥ 20 milyon TL) · açılıştan al · +%2'de sat, gelmezse kapanışta sat (maliyet %0,2 dahil). <i>Kağıt üzerinde takip, gerçek işlem yok.</i>", ""]
    if not yeni:
        L.append("Bugün kurala uyan hisse çıkmadı.")
    else:
        n = len(yeni); k = sum(x['hedef'] for x in yeni); ort = sum(x['getiri'] for x in yeni) / n
        L.append(f"<b>Bugün:</b> {n} aday · +%2 gören {k} (%{tr(k / n * 100, 0)}) · işlem başı ort. {pct(ort)}")
        b = [x for x in yeni if x['gap'] <= -5]
        if b: L.append(f"  Gap ≤ −%5 olanlar: {len(b)} · ort. {pct(sum(x['getiri'] for x in b) / len(b))}")
        L.append("")
        for x in yeni[:30]:
            iz = '✅' if x['hedef'] else '❌'
            L.append(f"{iz} <b>{x['sembol']}</b> gap {pct(x['gap'])} · açılış {tr(x['acilis'])} → {'+%2 ' + tr(x['acilis'] * 1.02) if x['hedef'] else 'kapanış ' + tr(x['kapanis'])} · {pct(x['getiri'])}")
        if len(yeni) > 30: L.append(f"… ve {len(yeni) - 30} hisse daha")
    if kayit:
        g = [float(x['getiri']) for x in kayit]; h = [int(x['hedef']) for x in kayit]; gunler = sorted(set(x['tarih'] for x in kayit))
        gun_ort = [sum(float(x['getiri']) for x in kayit if x['tarih'] == t) / max(1, sum(1 for x in kayit if x['tarih'] == t)) for t in gunler]
        b = [float(x['getiri']) for x in kayit if float(x['gap']) <= -5]
        L += ["", f"<b>Başlangıçtan beri</b> ({gunler[0][8:10]}.{gunler[0][5:7]} – {gg}, {len(gunler)} işlem günü):",
              f"{len(g)} işlem · +%2 gören %{tr(sum(h) / len(h) * 100, 0)} · işlem başı ort. {pct(sum(g) / len(g))} · kârlı gün %{tr(sum(1 for x in gun_ort if x > 0) / len(gun_ort) * 100, 0)}"]
        if b: L.append(f"Gap ≤ −%5: {len(b)} işlem · ort. {pct(sum(b) / len(b))}")
        L.append("Geriye dönük test beklentisi: +%2 görme ~%80, işlem başı ~+%0,8 (gap ≤ −%5: ~%86, ~+%1,1).")
    L += ["", "ℹ️ Kağıt üzerinde test, yatırım tavsiyesi değildir. Kaybeden işlemlerde kapanışa kadar tutulduğu için kayıp −%3/−%7 olabilir."]
    open(mesaj, 'w').write('\n'.join(L))
    print(f'{len(yeni)} aday; mesaj: {mesaj}')

if __name__ == '__main__':
    main()
