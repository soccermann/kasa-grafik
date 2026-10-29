# Gap-aşağı açılış takibi (kağıt üzerinde)
Kural: 09:55 açılış seansı fiyatı önceki kapanışın −%3 ile −%9,5 arası altında olan, 10 günlük ort. işlem hacmi ≥ 20 milyon TL hisseler.
Açılıştan al, +%2'de sat; +%2 gelmezse kapanışta sat. Maliyet %0,2.
- gun_sonu.py: hafta içi kapanış sonrası TradingView tarayıcısıyla günün adaylarını ve sonucunu hesaplar, islemler.csv'ye ekler, Telegram mesajı yazar.
- islemler.csv: tüm kağıt işlemler (tarih, sembol, gap, açılış, yüksek, düşük, kapanış, ciro_m, hedef 1/0, getiri %).
Geriye dönük test (Borsa İstanbul DataStore, Oca 2022–Eyl 2026, 7.036 işlem): +%2 görme %80, işlem başı +%0,77 (gap ≤ −%5: %86, +%1,13); her yıl pozitif.
15 dakikalık veriyle teyit (2026, 261 olay): açılıştan alım +%1,12; +%2'nin %76'sı 10:00–10:15 arasında.
Yatırım tavsiyesi değildir.

## Sabah sinyali (sabah_sinyal.py)
Hafta içi 09:57'de çalışan görev, GAP AŞAĞI ROBOTU (v8) kuralına giren 09:55 adaylarını filtreler
(dün %9+ düşen, 10 günde dipten %50+ şişmiş) ve her aday için geçmiş tetiklenmeleri + 5.000 gün içi simülasyonu
hesaplayıp Telegram'a yazar. Emir göndermez.

## Gap-yukarı denemesi (gap_yukari_backtest.py)
Gap-aşağı robotunun tersi: dün güçlü olan hisse bugün 09:55'te yukarı gaplı açılırsa açılıştan al, +%2 hedef,
gelmezse kapanışta sat. 249 likit hisse, TradingView günlük veri (Eki 2021 – Eki 2026), maliyet %0,2.
Sonuç: filtresiz gap-yukarı ZARARLI (işlem başı −%0,40). Asıl avantaj "dün tavan kapattı + bugün gap %1–%5"te:
3.474 işlem, +%2 görme %82, işlem başı +%0,49 net, her yıl pozitif. Ayrıntı: gap_yukari_rapor.md.
−%2 stop önerilmez: 5 dk veride hedef/stop çoğunlukla 10:00–10:05 mumunda belli oluyor, stop getiriyi iyileştirmiyor.
TradingView BIST'te hacim vermediği için hacim kriterleri veri eklenince çalışır. Yatırım tavsiyesi değildir.
