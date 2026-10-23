# Coin takip (haftalık kağıt portföy)

İki tarama her pazar izlenir: Düşük oynaklık + BTC filtresi (DUSUKVOL_90) ve Momentum + trend + BTC filtresi (MOMMA_30).
Gerçek işlem yok. Rapor sayfası: Claude artifact "Coin Takip Defteri".

Haftalık akış (W = çalışma klasörü):
1. 44 coinin her biri için TradingView get_ohlcv: BINANCE:<COIN>USDT, 1D, count 3000, format columns, date_to = dünün tarihi.
   Yanıtlar büyük olduğu için araç dosyaya kaydeder.
2. cd $W && python3 build_panel.py /root/.claude/projects <dünün tarihi>   -> trk_close.csv, trk_dv.csv
3. python3 tracker.py $W/trk_close.csv $W/trk_dv.csv tracker_log.json      (aynı tarih iki kez çalışırsa kayıt yenilenir)
4. python3 report.py tracker_log.json $W/report.html

## Tüm Binance (deneysel, 18 Ekim 2026'dan itibaren)
Aynı iki kural Binance'teki bütün likit coinlere uygulanır (tum_binance.py başındaki açıklamaya bak).
5. TradingView run_screener: market "crypto", filters {"24h_vol_cmc": [1000000, null]}, columns
   ["name","description","close","SMA50","Perf.W","Perf.1M","Perf.3M","ATR","24h_vol_cmc","crypto_common_categories.tr"],
   sort_by "24h_vol_cmc", limit 500 — bir kez sort_order "desc", bir kez "asc" (ikisi birlikte tüm listeyi kapsar).
6. python3 tum_binance.py aday <tarama_desc> <tarama_asc>   (çalışma klasöründe aday.json yazar)
7. Listeleme kontrolü ve binance_var.txt (tum_binance.py başındaki 2. adım).
8. python3 tum_binance.py kaydet aday.json binance_var.txt tracker_log.json tum_log.json
9. python3 report.py tracker_log.json $W/report.html tum_log.json
