"""
Tum Binance: ayni iki kural, Binance'te islem goren butun likit coinlere uygulanir.

Fark (44 coinlik takipten): veri TradingView coin taramasindan gelir, gunluk mum degil.
  - Oynaklik: 90 gunluk getiri sapmasi yerine 14 gunluk ATR / fiyat.
  - Likidite: 24 saatlik toplam hacim >= 1 milyon $ (tum borsalar).
  - Gecmis: 50 gunluk ortalamasi hesaplanabilen (en az ~50 gunluk) coinler.
  - Fiyatlar tarama anindaki fiyat (CRYPTO:XUSD, borsalar arasi ortalama).
  - Stablecoin, sarili (wrapped), staking, altin ve tokenize hisse/ETF tokenlari haric.
  - BTC filtresi 44 coinlik takiple ayni: o haftaki kaydin in_market degeri.
Bu kurallar gecmiste test edilmedi; sadece karsilastirma icin izlenir.

Kullanim:
  1) python3 tum_binance.py aday <tarama1.json> [<tarama2.json> ...]  -> aday.json + kontrol edilecek semboller
  2) Her listede siradan basla; her aday icin get_ohlcv BINANCE:<COIN>USDT, 1D, count 30, summary true.
     "invalid symbol" ise bir kez de sondaki harfi atilmis haliyle dene (HYPEH -> HYPE).
     Basarili olanlari binance_var.txt'ye bir satir olarak yaz: COIN BINANCE_TICKER last_close avg_volume
     (sayilar yanittaki summary'den AYNEN). Her listede 5 gecerli coin bulununca o listeyi birak.
     Gecerli = fiyat tarama fiyatina %5 icinde (ayni coin) VE avg_volume*last_close >= 1 milyon $.
     get_symbol_data_batch borsa ayrimi yapmaz, listeleme kontrolu icin kullanma.
  3) python3 tum_binance.py kaydet aday.json binance_var.txt tracker_log.json tum_log.json
"""
import json
import sys

K = 5
EXCL_CAT = {'Stablecoins', 'Wrapped tokens', 'Rehypothecated assets'}
EXCL = {'PAXG', 'XAUT', 'USD1W', 'FDUSD', 'TUSD', 'USDP', 'EURI', 'AEUR', 'BFUSD'}


def load_rows(files):
    rows = {}
    for f in files:
        for r in json.load(open(f))['data']['rows']:
            rows[r['symbol']] = r
    return rows


def aday(files):
    rows = load_rows(files)
    btc = rows['CRYPTO:BTCUSD']
    elig = {}
    for r in rows.values():
        t = r['name'][:-3]
        cats = set(r.get('crypto_common_categories.tr') or [])
        desc = (r.get('description') or '').lower()
        if t in EXCL or cats & EXCL_CAT or any(w in desc for w in ('tokenized', 'xstock', 'bstock')):
            continue
        if None in (r.get('close'), r.get('SMA50'), r.get('ATR'), r.get('Perf.1M'), r.get('Perf.W')) or r['close'] <= 0:
            continue
        elig[t] = {
            'coin': t, 'entry': r['close'],
            'ret_7g': round(r['Perf.W'], 1), 'ret_30g': round(r['Perf.1M'], 1),
            'btc_gore_30g': round(r['Perf.1M'] - btc['Perf.1M'], 1),
            'oynaklik_30g': round(r['ATR'] / r['close'] * 100, 2),   # burada: 14 gunluk ATR, fiyatin %'si
            'ma50_uzaklik': round((r['close'] / r['SMA50'] - 1) * 100, 1),
            'hacim_7_30': None,
            'vol24h_musd': round(r['24h_vol_cmc'] / 1e6, 1),
        }
    elig = {k: v for k, v in elig.items()          # fiyati sabit (stablecoin benzeri) olanlari at
            if not (v['oynaklik_30g'] < 0.3 and abs(v['ret_30g']) < 1)}
    low = sorted(elig.values(), key=lambda x: x['oynaklik_30g'])[:80]
    mom = sorted([x for x in elig.values() if x['ma50_uzaklik'] > 0], key=lambda x: -x['ret_30g'])[:80]
    out = {'n_eligible': len(elig), 'closes': {k: v['entry'] for k, v in elig.items()},
           'TUM_DUSUKVOL': low, 'TUM_MOMMA': mom}
    json.dump(out, open('aday.json', 'w'))
    syms = sorted({x['coin'] for x in low + mom})
    print('uygun coin:', len(elig))
    print('kontrol edilecek:', json.dumps([f'BINANCE:{s}USDT' for s in syms]))
    print('eslesmezse dene :', json.dumps([f'BINANCE:{s[:-1]}USDT' for s in syms]))


def kaydet(aday_path, var_path, main_log_path, log_path):
    a = json.load(open(aday_path))
    var = {}
    for l in open(var_path):
        p = l.split()
        if len(p) == 4:
            var[p[0].upper()] = (p[1].upper(), float(p[2]), float(p[3]))
    main = json.load(open(main_log_path))['weeks'][-1]
    try:
        log = json.load(open(log_path))
    except FileNotFoundError:
        log = {'start': main['date'], 'weeks': []}
    date = main['date']
    log['weeks'] = [w for w in log['weeks'] if w['date'] != date]
    picks = {}
    for key in ('TUM_DUSUKVOL', 'TUM_MOMMA'):
        ok = []
        for x in a[key]:
            v = var.get(x['coin'])
            if v and abs(v[1] / x['entry'] - 1) <= 0.05 and v[1] * v[2] >= 1e6:
                ok.append(dict(x, binance=v[0], binance_dv_musd=round(v[1] * v[2] / 1e6, 1)))
        picks[key] = ok[:K]
    log['weeks'].append({'date': date, 'in_market': main['in_market'],
                         'btc_close': main['btc_close'], 'btc_ma50': main['btc_ma50'],
                         'closes': a['closes'], 'eligible': list(a['closes']),
                         'n_eligible': a['n_eligible'], 'picks': picks})
    log['weeks'].sort(key=lambda w: w['date'])
    import tracker
    tracker.LISTS = {'TUM_DUSUKVOL': None, 'TUM_MOMMA': None}
    log['summary'] = tracker.summarize(log)
    json.dump(log, open(log_path, 'w'), indent=1)
    for k, v in picks.items():
        print(k, [x['coin'] for x in v])


if __name__ == '__main__':
    if sys.argv[1] == 'aday':
        aday(sys.argv[2:])
    else:
        kaydet(*sys.argv[2:6])
