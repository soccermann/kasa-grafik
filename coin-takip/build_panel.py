"""Kaydedilmis TradingView get_ohlcv cikti dosyalarindan kapanis ve dolar hacmi tablosu kurar.

Kullanim: python3 build_panel.py <arama_klasoru> <bitis_tarihi YYYY-MM-DD>
Cikti: trk_close.csv, trk_dv.csv (son 200 gun), eksik coin listesi ekrana.
"""
import glob
import json
import os
import sys
import pandas as pd

UNIVERSE = ['BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE', 'DOT', 'TRX', 'LTC', 'LINK', 'UNI',
            'ATOM', 'XLM', 'BCH', 'ETC', 'FIL', 'VET', 'ALGO', 'HBAR', 'AVAX', 'NEAR', 'XTZ',
            'THETA', 'NEO', 'IOTA', 'DASH', 'ZEC', 'LUNA', 'FTT', 'CHZ', 'ENJ', 'AAVE', 'SAND',
            'MANA', 'AXS', 'GRT', 'CRV', 'SNX', 'COMP', 'KSM', 'RUNE', 'EGLD', 'ZIL']

root, end = sys.argv[1], sys.argv[2]
C, V, seen = {}, {}, {}
for f in glob.glob(os.path.join(root, '**', 'mcp-tradingview-mcp-tv-get-ohlcv-*.txt'), recursive=True):
    try:
        j = json.load(open(f))
        s = j['symbol'].split(':')[1].replace('USDT', '')
    except Exception:
        continue
    if s not in UNIVERSE:
        continue
    b = pd.DataFrame(j['bars'])
    b['date'] = pd.to_datetime(b.t, unit='s').dt.normalize()
    b = b.drop_duplicates('date').set_index('date')
    seen.setdefault(s, []).append((os.path.getmtime(f), b))
for s, parts in seen.items():            # ayni coinin tum dosyalarini birlestir, cakisanda en yeni kazanir
    parts.sort(key=lambda x: x[0])
    allb = pd.concat([p[1] for p in parts])
    allb = allb[~allb.index.duplicated(keep='last')].sort_index()
    C[s], V[s] = allb.c, allb.c * allb.v
close = pd.DataFrame(C).sort_index()
close = close[close.index <= end].iloc[-200:]
dv = pd.DataFrame(V).reindex(close.index)
close.to_csv('trk_close.csv')
dv.to_csv('trk_dv.csv')
print('son tarih:', close.index[-1].date(), '| coin:', close.shape[1],
      '| eksik:', sorted(set(UNIVERSE) - set(close.columns)))
