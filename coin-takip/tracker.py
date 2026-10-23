"""
Haftalik kagit takip: Dusuk oynaklik + BTC filtresi ve Momentum + trend + BTC filtresi.

Kullanim:  python3 tracker.py coins_close.csv coins_dollarvol.csv tracker_log.json
  - CSV'ler: gunluk kapanis ve dolar hacmi (son en az 100 gun, sutun = coin).
  - Log yoksa olusturur; varsa son kapanis tarihini yeni hafta olarak ekler.
  - Ayni tarih tekrar calistirilirsa o haftanin kaydini yeniler (cift kayit olmaz).
Kurallar coin_screen.py ile birebir ayni: 5 coin, esit agirlik, BTC 50 gunluk
ortalamanin altindaysa nakit. Giris fiyati = sinyal gunu kapanisi. Maliyet: her
degisen pozisyon icin alis+satis 2 x 8 bps.
"""
import json
import sys
import numpy as np
import pandas as pd

K, MIN_HIST, MIN_DV, COST = 5, 60, 1e6, 0.0008
LISTS = {'DUSUKVOL_90': ('DUSUKVOL', 90), 'MOMMA_30': ('MOM+MA', 30)}
LABEL = {'DUSUKVOL_90': 'Düşük oynaklık + BTC filtresi',
         'MOMMA_30': 'Momentum + trend + BTC filtresi'}


def score(c, dv, family, L):
    hist = c.notna().cumsum()
    liq = dv.rolling(30, min_periods=20).mean()
    ok = (hist >= MIN_HIST) & (liq >= MIN_DV) & c.notna()
    if family == 'DUSUKVOL':
        s = -np.log(c / c.shift(1)).rolling(L).std()
    else:  # MOM+MA
        s = (c / c.shift(L) - 1).where(c > c.rolling(50).mean())
    return s.where(ok)


def features(c, dv, coin):
    x, b = c[coin], c['BTC']
    r = lambda s, n: s.iloc[-1] / s.iloc[-1 - n] - 1
    return {
        'ret_7g': round(r(x, 7) * 100, 1),
        'ret_30g': round(r(x, 30) * 100, 1),
        'btc_gore_30g': round((r(x, 30) - r(b, 30)) * 100, 1),
        'oynaklik_30g': round(np.log(x / x.shift(1)).iloc[-30:].std() * np.sqrt(365) * 100, 1),
        'ma50_uzaklik': round((x.iloc[-1] / x.iloc[-50:].mean() - 1) * 100, 1),
        'hacim_7_30': round(dv[coin].iloc[-7:].mean() / dv[coin].iloc[-30:].mean(), 2),
    }


def run(close_csv, dv_csv, log_path):
    c = pd.read_csv(close_csv, index_col=0, parse_dates=True).sort_index()
    dv = pd.read_csv(dv_csv, index_col=0, parse_dates=True).reindex(c.index)
    date = str(c.index[-1].date())
    try:
        log = json.load(open(log_path))
    except FileNotFoundError:
        log = {'start': date, 'weeks': []}
    log['weeks'] = [w for w in log['weeks'] if w['date'] != date]

    btc, ma = float(c['BTC'].iloc[-1]), float(c['BTC'].iloc[-50:].mean())
    week = {'date': date, 'btc_close': round(btc, 2), 'btc_ma50': round(ma, 2),
            'in_market': bool(btc > ma),
            'closes': {k: float(v) for k, v in c.iloc[-1].dropna().items()},
            'picks': {}}
    for key, (fam, L) in LISTS.items():
        s = score(c, dv, fam, L).iloc[-1].dropna().nlargest(K)
        week['picks'][key] = [{'coin': k, 'entry': float(c[k].iloc[-1]), **features(c, dv, k)}
                              for k in s.index]
    elig = score(c, dv, 'DUSUKVOL', 90).iloc[-1].dropna().index
    week['eligible'] = list(elig)
    log['weeks'].append(week)
    log['weeks'].sort(key=lambda w: w['date'])
    log['summary'] = summarize(log)
    json.dump(log, open(log_path, 'w'), indent=1)
    return log


def summarize(log):
    """Tamamlanmis her hafta: listelerin getirisi, BTC, esit agirlik; ortak ozellik analizi."""
    W = log['weeks']
    rows, picks_eval = [], []
    prev_hold = {k: set() for k in LISTS}
    for a, b in zip(W[:-1], W[1:]):
        row = {'from': a['date'], 'to': b['date'], 'in_market': a['in_market'],
               'btc': round((b['btc_close'] / a['btc_close'] - 1) * 100, 2)}
        er = [b['closes'][k] / a['closes'][k] - 1 for k in a.get('eligible', []) if k in b['closes']]
        row['esit_agirlik'] = round(float(np.mean(er)) * 100, 2) if er else None
        for key in LISTS:
            rets = []
            for p in a['picks'][key]:
                px = b['closes'].get(p['coin'])
                r = (px / p['entry'] - 1) if px else -1.0
                rets.append(r)
                picks_eval.append({'week': a['date'], 'list': key, 'coin': p['coin'],
                                   'ret': round(r * 100, 2),
                                   **{f: p[f] for f in p if f not in ('coin', 'entry')}})
            hold = {p['coin'] for p in a['picks'][key]} if a['in_market'] else set()
            changed = len(hold ^ prev_hold[key]) / K
            gross = float(np.mean(rets)) if (a['in_market'] and rets) else 0.0
            row[key] = round((gross - changed * COST) * 100, 2)
            row[key + '_aday'] = round(float(np.mean(rets)) * 100, 2) if rets else None
            prev_hold[key] = hold
        rows.append(row)
    cum = {}
    for col in ['btc', 'esit_agirlik'] + list(LISTS):
        v = [r[col] for r in rows if r.get(col) is not None]
        cum[col] = round((float(np.prod([1 + x / 100 for x in v])) - 1) * 100, 2) if v else 0.0
    traits = {}
    if picks_eval:
        df = pd.DataFrame(picks_eval)
        df['kazanan'] = df['ret'] > 0
        fcols = ['ret_7g', 'ret_30g', 'btc_gore_30g', 'oynaklik_30g', 'ma50_uzaklik', 'hacim_7_30']
        traits = {
            'n_picks': int(len(df)), 'win_rate_pct': round(df['kazanan'].mean() * 100, 1),
            'kazanan_medyan': df[df.kazanan][fcols].apply(pd.to_numeric, errors='coerce').median().round(2).dropna().to_dict(),
            'kaybeden_medyan': df[~df.kazanan][fcols].apply(pd.to_numeric, errors='coerce').median().round(2).dropna().to_dict(),
            'iki_listede_ortak': df.groupby(['week', 'coin'])['list'].nunique().ge(2).groupby('coin').sum()
                                   .loc[lambda s: s > 0].astype(int).to_dict(),
            'coin_ortalama': df.groupby('coin')['ret'].agg(['count', 'mean']).round(2)
                               .sort_values('mean', ascending=False).to_dict('index'),
        }
    return {'weeks_done': len(rows), 'rows': rows, 'cumulative_pct': cum,
            'traits': traits, 'picks_eval': picks_eval}


if __name__ == '__main__':
    out = run(*sys.argv[1:4])
    print(json.dumps({k: out['summary'][k] for k in ('weeks_done', 'cumulative_pct')}, indent=1))
    print(json.dumps(out['weeks'][-1]['picks'], indent=1))
