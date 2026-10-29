"""GAP-YUKARI BACKTEST: gap-aşağı robotunun tersi.

Fikir: dün GÜÇLÜ görünen bir hisse bugün 09:55 açılış eşleşmesinde yukarı gaplı açılırsa açılıştan al,
+%2 hedefte sat; hedef gelmezse kapanışta sat (isteğe bağlı −%2 stop). Emir göndermez, yalnızca hesap yapar.

Kullanım:
  python3 gap_yukari_backtest.py GUNLUK.json [--gap 1,7] [--hedef 2] [--stop 2] [--maliyet 0.2]
                                 [--ayrim 2025-01-01] [--csv olaylar.csv] [--rapor rapor.md]
GUNLUK.json: {"SEMBOL": {"t":[unix sn], "o":[...], "h":[...], "l":[...], "c":[...], "v":[... isteğe bağlı]}, ...}
  (TradingView mcp-tv-get-ohlcv 1D çıktılarından derlenir.) "v" (adet hacim) varsa hacim kriterleri
  otomatik devreye girer; TradingView BIST'te hacim vermediği için şu an yalnızca fiyat kriterleri çalışır.

Sonuç hesabı (günlük mumla):
  giriş   = bugünün açılışı (09:55 eşleşme fiyatı)
  hedef   = giriş × (1 + hedef%)  fiyat adımına yukarı yuvarlanır
  stopsuz : gün yükseği ≥ hedef ise +hedef, değilse kapanış getirisi              → günlük veriyle KESİN
  stoplu  : aynı gün hem hedef hem stop görüldüyse hangisinin önce geldiği günlük mumdan bilinmez:
            'kötümser' önce stop, 'iyimser' önce hedef sayar. Gerçek sonuç ikisinin arasındadır.
  maliyet : işlem başı gidiş-dönüş % (varsayılan %0,2), getiriden düşülür.
BIST tavan kuralı: fiyat önceki kapanışın en fazla +%10'u olabilir. Gap > ~%7,8 iken +%2 hedef tavanı aşar,
  yani hedef imkânsızdır; bu yüzden varsayılan gap aralığı %1–%7.
"""
import sys, json, math, csv
from datetime import datetime, timezone, timedelta
from collections import defaultdict

TZ = timezone(timedelta(hours=3))


def tik(p):
    return .01 if p < 20 else .02 if p < 50 else .05 if p < 100 else .1 if p < 250 else .25 if p < 500 \
        else .5 if p < 1000 else 1 if p < 2500 else 2.5


def tik_yukari(x):
    t = tik(x)
    if t / x > 0.005:   # bölünme düzeltmeli eski fiyatlarda (ör. 0,30 TL) adım gerçek değil; yuvarlama yapma
        return x
    return round(math.ceil(x / t - 1e-9) * t, 4)


def tik_asagi(x):
    t = tik(x)
    if t / x > 0.005:
        return x
    return round(math.floor(x / t + 1e-9) * t, 4)


# ---------------------------------------------------------------- göstergeler (yalnızca DÜNE kadarki veri)
def ozellikler(o, h, l, c, v, i):
    """i: işlem günü (bugün). Tüm özellikler i-1 ve öncesinden hesaplanır (ileriye bakma yok)."""
    d = i - 1
    if d < 60:
        return None
    rng = h[d] - l[d]
    tr = [max(h[k] - l[k], abs(h[k] - c[k - 1]), abs(l[k] - c[k - 1])) for k in range(d - 14, d)]
    atr = sum(tr) / 14
    sma20 = sum(c[d - 19:d + 1]) / 20
    sma50 = sum(c[d - 49:d + 1]) / 50
    f = {}
    f['dun_getiri'] = (c[d] / c[d - 1] - 1) * 100
    f['dun2_getiri'] = (c[d - 1] / c[d - 2] - 1) * 100
    f['clv'] = (c[d] - l[d]) / rng if rng > 0 else 0.5            # kapanışın gün aralığındaki yeri (1 = tepe)
    f['govde'] = abs(c[d] - o[d]) / rng if rng > 0 else 0          # gövde / aralık
    f['yesil'] = c[d] > o[d]
    f['alt_fitil'] = (min(o[d], c[d]) - l[d]) / rng if rng > 0 else 0
    f['ust_fitil'] = (h[d] - max(o[d], c[d])) / rng if rng > 0 else 0
    f['aralik_atr'] = rng / atr if atr > 0 else 0                  # aralık genişlemesi (hacim vekili)
    f['kirilim20'] = c[d] > max(h[d - 20:d])                       # 20 günlük zirve kırılımı (kapanışla)
    f['kirilim55'] = c[d] > max(h[max(0, d - 55):d])
    f['zirveye_uzak20'] = (c[d] / max(h[d - 19:d + 1]) - 1) * 100
    f['dipten20'] = (c[d] / min(l[d - 19:d + 1]) - 1) * 100
    f['dip_yakin'] = min(l[d - 2:d + 1]) <= min(l[d - 19:d + 1]) * 1.0001   # son 3 günde 20g dip yapılmış
    f['sma20_ustu'] = c[d] > sma20
    f['sma50_ustu'] = c[d] > sma50
    f['sma20_kesti'] = c[d] > sma20 and c[d - 1] <= sum(c[d - 20:d]) / 20
    f['yutan'] = c[d] > o[d] and c[d - 1] < o[d - 1] and c[d] >= o[d - 1] and o[d] <= c[d - 1]   # boğa yutan
    f['cekic'] = f['alt_fitil'] >= 0.55 and f['clv'] >= 0.6                  # çekiç / dipten dönüş mumu
    dusus = 0
    for k in range(d - 1, d - 8, -1):
        if c[k] < c[k - 1]: dusus += 1
        else: break
    f['onceki_dusus_gunu'] = dusus                                            # dünden önce art arda düşüş
    f['tavan'] = f['dun_getiri'] >= 9.5 and c[d] >= h[d] - 1e-9               # dün tavan kapattı
    f['getiri5'] = (c[d] / c[d - 5] - 1) * 100
    f['getiri20'] = (c[d] / c[d - 20] - 1) * 100
    if v is not None and all(v[k] for k in range(d - 20, d + 1)):
        ort = sum(v[d - 20:d]) / 20
        f['hacim_kat'] = v[d] / ort if ort > 0 else None                      # dün hacmi / 20g ort.
    else:
        f['hacim_kat'] = None
    return f


# ---------------------------------------------------------------- kriterler
KRITERLER = {
    'TÜMÜ (filtresiz)':                 lambda f: True,
    'Dün yükseldi (>0)':                lambda f: f['dun_getiri'] > 0,
    'Dün %2+ yükseldi':                 lambda f: f['dun_getiri'] >= 2,
    'Dün %4+ yükseldi':                 lambda f: f['dun_getiri'] >= 4,
    'Dün düştü (<0)':                   lambda f: f['dun_getiri'] < 0,
    'Dün tavan kapattı':                lambda f: f['tavan'],
    'Güçlü kapanış (clv≥0,8)':          lambda f: f['clv'] >= 0.8,
    'Zayıf kapanış (clv≤0,3)':          lambda f: f['clv'] <= 0.3,
    'Yeşil marubozu (gövde≥0,7)':       lambda f: f['yesil'] and f['govde'] >= 0.7,
    'Aralık genişlemesi (≥1,5 ATR)':    lambda f: f['aralik_atr'] >= 1.5,
    'Geniş+güçlü (≥1,5ATR, clv≥0,7)':   lambda f: f['aralik_atr'] >= 1.5 and f['clv'] >= 0.7 and f['yesil'],
    '20g zirve kırılımı':               lambda f: f['kirilim20'],
    '55g zirve kırılımı':               lambda f: f['kirilim55'],
    'Kırılım + güçlü kapanış':          lambda f: f['kirilim20'] and f['clv'] >= 0.7,
    'SMA20 üstü':                       lambda f: f['sma20_ustu'],
    'SMA20 altı':                       lambda f: not f['sma20_ustu'],
    'SMA20 yukarı kesti':               lambda f: f['sma20_kesti'],
    'SMA20 ve SMA50 üstü':              lambda f: f['sma20_ustu'] and f['sma50_ustu'],
    'Boğa yutan':                       lambda f: f['yutan'],
    'Çekiç (dipten dönüş mumu)':        lambda f: f['cekic'],
    'Dipten dönüş (20g dip + yeşil)':   lambda f: f['dip_yakin'] and f['yesil'] and f['clv'] >= 0.6,
    '2+ gün düşüş sonrası yeşil':       lambda f: f['onceki_dusus_gunu'] >= 2 and f['dun_getiri'] > 0,
    'Son 20g %20+ yükselmiş (şişmiş)':  lambda f: f['getiri20'] >= 20,
    'Son 20g düşmüş':                   lambda f: f['getiri20'] < 0,
    'Hacim 2x+ (hacim varsa)':          lambda f: f['hacim_kat'] is not None and f['hacim_kat'] >= 2,
    'Hacim 2x+ ve güçlü kapanış':       lambda f: f['hacim_kat'] is not None and f['hacim_kat'] >= 2 and f['clv'] >= 0.7,
}


# ---------------------------------------------------------------- olayları üret
def olaylar(veri, gmin, gmax, hedef, stop, maliyet):
    out = []
    for sym, d in veri.items():
        t, o, h, l, c = d['t'], d['o'], d['h'], d['l'], d['c']
        v = d.get('v')
        if v is not None and not any(v):
            v = None
        n = len(t)
        for i in range(61, n):
            if None in (o[i], h[i], l[i], c[i], c[i - 1]) or c[i - 1] <= 0:
                continue
            gap = (o[i] / c[i - 1] - 1) * 100
            if not (gmin <= gap <= gmax):
                continue
            if h[i] == l[i]:            # kilitli gün (tavan/taban açılıp hiç işlem görmeyen): alım mümkün değil
                continue
            f = ozellikler(o, h, l, c, v, i)
            if f is None:
                continue
            giris = o[i]
            tp = tik_yukari(giris * (1 + hedef / 100))
            sl = tik_asagi(giris * (1 - stop / 100)) if stop else None
            hedef_gordu = h[i] >= tp
            kap = (c[i] / giris - 1) * 100
            r_stopsuz = (tp / giris - 1) * 100 if hedef_gordu else kap
            if sl:
                stop_gordu = l[i] <= sl
                r_stop_s = (sl / giris - 1) * 100 if stop_gordu else r_stopsuz            # kötümser
                r_stop_i = (tp / giris - 1) * 100 if hedef_gordu else ((sl / giris - 1) * 100 if stop_gordu else kap)
            else:
                stop_gordu = False; r_stop_s = r_stop_i = r_stopsuz
            out.append(dict(tarih=datetime.fromtimestamp(t[i], TZ).strftime('%Y-%m-%d'), sym=sym, gap=gap,
                            giris=giris, hedef=hedef_gordu, stop=stop_gordu, kap=kap,
                            r=r_stopsuz - maliyet, r_kotu=r_stop_s - maliyet, r_iyi=r_stop_i - maliyet,
                            tavan_kapasite=(c[i - 1] * 1.10 / giris - 1) * 100, **f))
    out.sort(key=lambda x: (x['tarih'], x['sym']))
    return out


def ozet(xs):
    n = len(xs)
    if not n:
        return None
    hit = sum(x['hedef'] for x in xs) / n * 100
    ort = sum(x['r'] for x in xs) / n
    kotu = sum(x['r_kotu'] for x in xs) / n
    iyi = sum(x['r_iyi'] for x in xs) / n
    kaz = sum(1 for x in xs if x['r'] > 0) / n * 100
    rs = sorted(x['r'] for x in xs)
    return dict(n=n, hit=hit, ort=ort, kotu=kotu, iyi=iyi, kaz=kaz, med=rs[n // 2],
                gunler=len(set(x['tarih'] for x in xs)))


def tr(x, k=2):
    return f"{x:,.{k}f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def isaretli(x, k=2):
    return ('+' if x > 0 else '−' if x < 0 else '') + tr(abs(x), k)


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith('-'):
        print(__doc__); sys.exit(1)

    def arg(ad, vars_):
        return a[a.index(ad) + 1] if ad in a else vars_
    gmin, gmax = map(float, arg('--gap', '1,7').split(','))
    hedef = float(arg('--hedef', 2)); stop = float(arg('--stop', 2)); maliyet = float(arg('--maliyet', 0.2))
    ayrim = arg('--ayrim', '2025-01-01')
    veri = json.load(open(a[0]))
    ev = olaylar(veri, gmin, gmax, hedef, stop, maliyet)
    if '--csv' in a:
        with open(arg('--csv', ''), 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(ev[0].keys())); w.writeheader(); w.writerows(ev)
    hacim_var = any(x['hacim_kat'] is not None for x in ev)
    L = []
    ilk = min(x['tarih'] for x in ev); son = max(x['tarih'] for x in ev)
    L.append(f"# Gap-yukarı backtest · {len(veri)} hisse · {ilk} → {son}")
    L.append(f"Kural: gap %{tr(gmin,1)}…%{tr(gmax,1)} · açılıştan al · hedef +%{tr(hedef,1)} · "
             f"stop −%{tr(stop,1)} · maliyet %{tr(maliyet,1)} · eğitim < {ayrim} ≤ test")
    if not hacim_var:
        L.append("Hacim verisi yok → hacim kriterleri boş kalır.")
    L.append('')
    L.append("| Kriter (dünkü mum) | İşlem | +%2 gördü | Ort. net (stopsuz) | Stoplu kötümser…iyimser | Kazanan % | Eğitim ort. | Test ort. |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    taban = ozet(ev)
    sat = []
    for ad, fn in KRITERLER.items():
        xs = [x for x in ev if fn(x)]
        s = ozet(xs)
        if not s or s['n'] < 30:
            if s is None and 'Hacim' in ad and not hacim_var:
                continue
            sat.append((ad, s, None, None)); continue
        e = ozet([x for x in xs if x['tarih'] < ayrim]); te = ozet([x for x in xs if x['tarih'] >= ayrim])
        sat.append((ad, s, e, te))
    for ad, s, e, te in sat:
        if not s:
            L.append(f"| {ad} | 0 | | | | | | |"); continue
        if s['n'] < 30:
            L.append(f"| {ad} | {s['n']} | (az örnek) | | | | | |"); continue
        L.append(f"| {ad} | {s['n']:,} | %{tr(s['hit'],1)} | {isaretli(s['ort'])} | {isaretli(s['kotu'])} … {isaretli(s['iyi'])} | "
                 f"%{tr(s['kaz'],0)} | {isaretli(e['ort']) if e else '-'} | {isaretli(te['ort']) if te else '-'} |")
    # öne çıkan kural: dün tavan kapatan + bugün %1–%5 gap
    aday = [x for x in ev if x['tavan'] and x['gap'] < 5]
    if aday:
        L.append(''); L.append("## Öne çıkan kural: DÜN TAVAN KAPATTI + bugün gap %1–%5 (stopsuz)")
        s = ozet(aday); rs = sorted(x['r'] for x in aday)
        L.append(f"- {s['n']:,} işlem / {s['gunler']:,} gün · +%2 gördü %{tr(s['hit'],1)} · ort. net {isaretli(s['ort'])} · "
                 f"en kötü %5'lik dilim ≤ {isaretli(rs[int(len(rs) * .05)])}")
        for ad, fn in [('Son 20g %40+ yükselmiş', lambda x: x['getiri20'] >= 40),
                       ('Üst üste 2. tavan', lambda x: x['dun2_getiri'] >= 9.5),
                       ('İlk tavan', lambda x: x['dun2_getiri'] < 9.5)]:
            q = ozet([x for x in aday if fn(x)])
            if q:
                L.append(f"- {ad}: {q['n']:,} işlem · +%2 %{tr(q['hit'],1)} · ort. net {isaretli(q['ort'])}")
        yy = defaultdict(list)
        for x in aday: yy[x['tarih'][:4]].append(x)
        L.append('- Yıllar: ' + ' · '.join(f"{y} {isaretli(ozet(v)['ort'])} ({ozet(v)['n']})" for y, v in sorted(yy.items())))
    # gap dilimleri
    L.append(''); L.append("## Gap büyüklüğüne göre (filtresiz)")
    L.append("| Gap | İşlem | +%2 gördü | Ort. net | Stoplu kötümser…iyimser |"); L.append("|---|---:|---:|---:|---:|")
    sinir = [gmin] + [x for x in (2, 3, 4, 5, 6) if gmin < x < gmax] + [gmax]
    for lo, hi in zip(sinir, sinir[1:]):
        s = ozet([x for x in ev if lo <= x['gap'] < hi or (hi == gmax and x['gap'] == gmax)])
        if s:
            L.append(f"| %{tr(lo,0)}–%{tr(hi,0)} | {s['n']:,} | %{tr(s['hit'],1)} | {isaretli(s['ort'])} | {isaretli(s['kotu'])} … {isaretli(s['iyi'])} |")
    # yıllar
    L.append(''); L.append("## Yıllara göre (filtresiz)")
    L.append("| Yıl | İşlem | +%2 gördü | Ort. net |"); L.append("|---|---:|---:|---:|")
    yil = defaultdict(list)
    for x in ev: yil[x['tarih'][:4]].append(x)
    for y in sorted(yil):
        s = ozet(yil[y]); L.append(f"| {y} | {s['n']:,} | %{tr(s['hit'],1)} | {isaretli(s['ort'])} |")
    metin = '\n'.join(L)
    if '--rapor' in a:
        open(arg('--rapor', ''), 'w').write(metin)
    print(metin)


if __name__ == '__main__':
    main()
