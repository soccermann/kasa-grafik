"""Gap-aşağı SABAH SİNYALİ — GAP AŞAĞI ROBOTU (v8) kuralının 09:55 adaylarını filtreler ve
her aday için "zaman makinesi" oranlarını hesaplar (geçmiş tetiklenmeler + gün içi simülasyon).
Emir göndermez; yalnızca hesap yapar ve Telegram mesajı yazar.

Kullanım:
  python3 sabah_sinyal.py adaylar SCREENER.json [--haric SYM1,SYM2]
      -> robot kuralına giren adayları yazdırır (her satır: SEMBOL gap ciro_m). Son satır: ADAYLAR=SYM1,SYM2,...
  python3 sabah_sinyal.py rapor BUGUN --bar SYM=DOSYA [--bar SYM=DOSYA ...] [--screener SCREENER.json]
                          [--mesaj CIKTI.txt] [--sim 5000] [--seed 19]
      -> her sembolün 5 dakikalık verisiyle (mcp-tv-get-ohlcv, interval 5m, count 8000, format columns
         yanıtı; araç dosyaya kaydettiyse o dosya) filtreleri ve oranları hesaplar, mesajı yazar.
BUGUN: YYYY-MM-DD (İstanbul). Bugünün yalnızca 09:55 mumu kullanılır; sonraki mumlar hesaba girmez.

Robot kuralı (v8): 09:55 gapı -%9 ile -%5 arası, 10 günlük ort. ciro >= 20 mn TL, önceki gün düşüşü %9'dan az,
alış = açılış fiyatı, hedef +%2 (fiyat adımına yukarı), stop -%2 (aşağı), hedef/stop gelmezse 17:45'te sat.
Yeni filtre (öneri): son 10 günde dipten %50+ yükselmiş (şişmiş) hisseyi alma.
"""
import sys, json, os, random
from datetime import datetime, timezone, timedelta

GAP_ALT, GAP_UST = -9.0, -5.0
MIN_CIRO = 20e6
DUN_ESIK = -9.0
POMPA_ESIK, POMPA_GUN = 50.0, 10
HEDEF, STOP = 2.0, 2.0
CIKIS_SLOT = 94            # 17:45 (09:55 + 94*5 dk)
K = 100
TZ = timezone(timedelta(hours=3))
AYLAR = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']


def json_oku(yol):
    d = json.load(open(yol))
    if isinstance(d, list):
        d = json.loads(''.join(x.get('text', '') for x in d))
    if isinstance(d, str):
        d = json.loads(d)
    return d


def screener_satirlari(yol):
    d = json_oku(yol)
    if 'data' in d:
        d = d['data']
    return d['rows']


def barlar(yol):
    d = json_oku(yol)
    b = d.get('bars') or (d.get('data') or {}).get('bars')
    if b is None:
        raise ValueError('bars yok')
    if isinstance(b, list):
        return [(x['t'], x['o'], x['h'], x['l'], x['c']) for x in b]
    return list(zip(b['t'], b['o'], b['h'], b['l'], b['c']))


def tik(p):
    return .01 if p < 20 else .02 if p < 50 else .05 if p < 100 else .1 if p < 250 else .25 if p < 500 \
        else .5 if p < 1000 else 1 if p < 2500 else 2.5


def tik_yukari(x):
    t = tik(x); import math
    return round(math.ceil(x / t - 1e-9) * t, 4)


def tik_asagi(x):
    t = tik(x); import math
    return round(math.floor(x / t + 1e-9) * t, 4)


def seanslar(bars):
    gunler = {}
    for t, o, h, l, c in sorted(bars):
        if o is None or c is None or o <= 0:
            continue
        dt = datetime.fromtimestamp(t, TZ)
        dk = dt.hour * 60 + dt.minute
        if dk < 590 or dk > 1100:
            continue
        slot = max(0, min(K - 1, round((dk - 595) / 5)))
        gunler.setdefault(dt.strftime('%Y-%m-%d'), []).append(
            dict(o=o, h=max(h, o, c), l=min(l, o, c), c=c, slot=slot))
    ss = [dict(tarih=k, bars=v) for k, v in sorted(gunler.items())]
    for i, s in enumerate(ss):
        b = s['bars']
        s['acilis'], s['kapanis'] = b[0]['o'], b[-1]['c']
        s['yuksek'], s['dusuk'] = max(x['h'] for x in b), min(x['l'] for x in b)
        s['kilitli'] = s['yuksek'] == s['dusuk']
        p = ss[i - 1] if i else None
        s['onceki'] = p['kapanis'] if p else None
        s['gap'] = (s['acilis'] / p['kapanis'] - 1) * 100 if p else None
        s['degisim'] = (s['kapanis'] / p['kapanis'] - 1) * 100 if p else None
        s['taban'] = s['degisim'] is not None and s['degisim'] <= -9 and s['kapanis'] <= s['dusuk'] + 1e-9
    return ss


def pompa(kapanislar):
    mn, en = None, 0.0
    for c in kapanislar:
        mn = c if mn is None else min(mn, c)
        en = max(en, (c / mn - 1) * 100)
    return en


def oranlar(s):
    """Simülasyon için: her 5 dk mumun bir önceki kapanışa oranı."""
    by = [None] * K
    for b in s['bars']:
        by[b['slot']] = b
    pc = by[0]['c'] if by[0] else s['acilis']
    r = [(1, 1, 1, 1)] * K
    for k in range(1, K):
        b = by[k]
        if b:
            r[k] = (b['o'] / pc, b['h'] / pc, b['l'] / pc, b['c'] / pc)
            pc = b['c']
    return r


def islem(ss, i):
    """Robot kuralıyla geçmiş bir tetiklenmenin sonucu (gün içi, 17:45 çıkış; kilitli günde satış yok)."""
    giris = ss[i]['acilis']
    tp, sl = tik_yukari(giris * (1 + HEDEF / 100)), tik_asagi(giris * (1 - STOP / 100))
    for d in range(i, len(ss)):
        s = ss[d]
        for j, b in enumerate(s['bars']):
            if d == i and j == 0:
                continue
            if s['kilitli']:
                continue
            if b['slot'] >= CIKIS_SLOT:
                return 'kapanis', b['o'] / giris - 1
            if b['o'] >= tp: return 'hedef', b['o'] / giris - 1
            if b['o'] <= sl: return 'stop', b['o'] / giris - 1
            if b['l'] <= sl: return 'stop', sl / giris - 1
            if b['h'] >= tp: return 'hedef', tp / giris - 1
        if not s['kilitli'] and len(s['bars']) > 1 and d < len(ss) - 1:
            return 'kapanis', s['kapanis'] / giris - 1
    return 'acik', ss[-1]['kapanis'] / giris - 1


def simule(havuz, gap, n, seed):
    pc = 1 / (1 + gap / 100); lo, hi = pc * 0.9, pc * 1.1
    tg, st = 1 + HEDEF / 100, 1 - STOP / 100
    say = [0, 0, 0]; top = 0.0
    rng = random.Random(seed)
    for _ in range(n):
        p = 1.0; out = None
        for k in range(1, K):
            r = havuz[int(rng.random() * len(havuz))][k]
            o = min(hi, max(lo, p * r[0])); h = min(hi, max(lo, p * r[1]))
            l = min(hi, max(lo, p * r[2])); c = min(hi, max(lo, p * r[3]))
            h = max(h, o, c); l = min(l, o, c)
            if k >= CIKIS_SLOT: out = (2, o); break
            if o >= tg: out = (0, o); break
            if o <= st: out = (1, o); break
            if l <= st: out = (1, st); break
            if h >= tg: out = (0, tg); break
            p = c
        if out is None: out = (2, p)
        say[out[0]] += 1; top += out[1] - 1
    return [x / n * 100 for x in say], top / n * 100


def tr(x, n=1):
    return f"{x:,.{n}f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def yuz(x, n=1):
    return ('+' if x > 0 else '−' if x < 0 else '') + '%' + tr(abs(x), n)


def tarih_tr(k):
    return f"{int(k[8:10])} {AYLAR[int(k[5:7]) - 1]}"


def analiz(sym, yol, bugun, scr_row, nsim, seed):
    ss = seanslar(barlar(yol))
    gecmis = [s for s in ss if s['tarih'] < bugun]
    bugunku = next((s for s in ss if s['tarih'] == bugun), None)
    if len(gecmis) < 3:
        return dict(sym=sym, hata='yetersiz geçmiş veri')
    dun = gecmis[-1]
    if bugunku:
        acilis = bugunku['bars'][0]['o']
    elif scr_row and scr_row.get('open'):
        acilis = float(scr_row['open'])
    else:
        return dict(sym=sym, hata='bugünün açılış verisi yok')
    gap = (acilis / dun['kapanis'] - 1) * 100
    ciro = None
    if scr_row and scr_row.get('average_volume_10d_calc') and scr_row.get('close'):
        ciro = float(scr_row['average_volume_10d_calc']) * float(scr_row['close'])
    neden = []
    if not (GAP_ALT - 1e-9 <= gap <= GAP_UST + 1e-9): neden.append(f'gap {yuz(gap)} aralık dışı')
    if ciro is not None and ciro < MIN_CIRO: neden.append(f'ciro {tr(ciro / 1e6, 0)} mn TL')
    if dun['degisim'] is not None and dun['degisim'] <= DUN_ESIK:
        neden.append('dün ' + ('taban kapattı' if dun['taban'] else f"{yuz(dun['degisim'])} düştü"))
    pmp = pompa([s['kapanis'] for s in gecmis[-POMPA_GUN:]]) if len(gecmis) >= POMPA_GUN else 0
    sisme = pmp >= POMPA_ESIK
    # geçmiş tetiklenmeler (robotun alacağı günler)
    sonuc = {'hedef': 0, 'stop': 0, 'kapanis': 0, 'acik': 0}; rets = []
    for i in range(1, len(gecmis)):
        s = gecmis[i]
        if s['gap'] is None or not (GAP_ALT <= s['gap'] <= GAP_UST): continue
        if gecmis[i - 1]['degisim'] is not None and gecmis[i - 1]['degisim'] <= DUN_ESIK: continue
        k, r = islem(gecmis, i); sonuc[k] += 1; rets.append(r * 100)
    # simülasyon havuzu: bu hissenin gap-aşağı (≤ −%3) günleri, yetmezse tüm günleri
    havuz = [oranlar(s) for s in gecmis if s['gap'] is not None and s['gap'] <= -3]
    havuz_ad = 'gap-aşağı günleri'
    if len(havuz) < 5:
        havuz = [oranlar(s) for s in gecmis]; havuz_ad = 'tüm günleri'
    sim, sim_ort = simule(havuz, gap, nsim, seed)
    return dict(sym=sym, gap=gap, acilis=acilis, ciro=ciro, neden=neden, sisme=sisme, pompa=pmp,
                gecmis_n=len(rets), sonuc=sonuc, gecmis_ort=(sum(rets) / len(rets) if rets else None),
                sim=sim, sim_ort=sim_ort, havuz_n=len(havuz), havuz_ad=havuz_ad, seans=len(gecmis))


def rapor(a):
    bugun = a[0]
    dosyalar, scr, mesaj, nsim, seed = [], None, None, 5000, 19
    i = 1
    while i < len(a):
        if a[i] == '--bar': s, y = a[i + 1].split('=', 1); dosyalar.append((s.upper().replace('BIST:', ''), y)); i += 2
        elif a[i] == '--screener': scr = a[i + 1]; i += 2
        elif a[i] == '--mesaj': mesaj = a[i + 1]; i += 2
        elif a[i] == '--sim': nsim = int(a[i + 1]); i += 2
        elif a[i] == '--seed': seed = int(a[i + 1]); i += 2
        else: i += 1
    satir = {}
    if scr:
        for r in screener_satirlari(scr):
            satir[str(r.get('name', '')).upper()] = r
    sonuclar = []
    for sym, yol in dosyalar:
        try:
            sonuclar.append(analiz(sym, yol, bugun, satir.get(sym), nsim, seed))
        except Exception as e:
            sonuclar.append(dict(sym=sym, hata=f'veri okunamadı ({e})'))
    al = [r for r in sonuclar if 'hata' not in r and not r['neden'] and not r['sisme']]
    sis = [r for r in sonuclar if 'hata' not in r and not r['neden'] and r['sisme']]
    red = [r for r in sonuclar if 'hata' not in r and r['neden']]
    hata = [r for r in sonuclar if 'hata' in r]
    L = [f"<b>Gap-aşağı sabah sinyali · {tarih_tr(bugun)} 09:55</b>",
         f"Robot kuralı: gap −%9…−%5 · hedef +%2 · stop −%2 · 17:45 çıkış",
         f"Aday {len(sonuclar)} · robot alır {len(al) + len(sis)} · şişme filtresi eler {len(sis)} · elenen {len(red)}", ""]

    def blok(r, isaret):
        s = r['sonuc']
        L.append(f"{isaret} <b>{r['sym']}</b> gap {yuz(r['gap'])} · açılış {tr(r['acilis'], 2)}"
                 + (f" · ciro {tr(r['ciro'] / 1e6, 0)} mn" if r['ciro'] else ''))
        if r['gecmis_n']:
            L.append(f"   Geçmiş ({r['seans']} seans): {r['gecmis_n']} tetik → {s['hedef']} hedef / {s['stop']} stop / "
                     f"{s['kapanis'] + s['acik']} kapanış · ort {yuz(r['gecmis_ort'], 2)}")
        else:
            L.append(f"   Geçmiş ({r['seans']} seans): bu kuralla tetiklenme yok")
        h, st, k = r['sim']
        L.append(f"   Simülasyon: hedef %{tr(h, 0)} · stop %{tr(st, 0)} · 17:45 %{tr(k, 0)} · ort {yuz(r['sim_ort'], 2)}"
                 f" ({r['havuz_ad']}, {r['havuz_n']} gün)")
        if r['sisme']:
            L.append(f"   Son {POMPA_GUN} günde dipten {yuz(r['pompa'], 0)} yükselmiş (şişme filtresi)")

    for r in sorted(al, key=lambda x: -x['sim'][0]): blok(r, '✅')
    for r in sis: blok(r, '⚠️')
    if red:
        L.append('')
        L.append('<b>Elenenler</b>')
        for r in red:
            L.append(f"⛔ {r['sym']} gap {yuz(r['gap'])} · {', '.join(r['neden'])}")
    if hata:
        L.append('')
        L.append('Veri alınamayan: ' + ', '.join(f"{r['sym']} ({r['hata']})" for r in hata))
    L.append('')
    L.append('<i>Oranlar son ~57 seansın 5 dk mumlarından; tahmin değil, geçmişin tekrarıdır. Yatırım tavsiyesi değildir.</i>')
    metin = '\n'.join(L)
    if mesaj:
        open(mesaj, 'w').write(metin)
    print(metin)


def adaylar(a):
    scr = a[0]; haric = set()
    if '--haric' in a:
        haric = set(s.strip().upper() for s in a[a.index('--haric') + 1].split(',') if s.strip())
    secilen = []
    for r in screener_satirlari(scr):
        try:
            s = str(r['name']).upper(); g = float(r['gap'])
            ciro = float(r['average_volume_10d_calc']) * float(r['close'])
        except (KeyError, TypeError, ValueError):
            continue
        if s in haric or not (GAP_ALT - 0.05 <= g <= GAP_UST + 0.05) or ciro < MIN_CIRO:
            continue
        secilen.append((s, g, ciro))
    secilen.sort(key=lambda x: -x[2])
    for s, g, c in secilen:
        print(f"{s} {g:.2f} {c / 1e6:.0f}")
    print('ADAYLAR=' + ','.join(s for s, _, _ in secilen))


if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] not in ('adaylar', 'rapor'):
        print(__doc__); sys.exit(1)
    (adaylar if sys.argv[1] == 'adaylar' else rapor)(sys.argv[2:])
