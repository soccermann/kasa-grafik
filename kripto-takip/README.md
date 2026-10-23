# Kripto takip: sıkışma + hacim kıvılcımı

Binance USDT paritelerinde 1 saatlik mumlarla tarama (TradingView verisi).
- `semboller.txt` – taranan pariteler
- `onfiltre.py` – toplu sorgudan adayları seçer (4s Bollinger sıkışması + son 1–4 saatte kıpırdanma)
- `tara.py` – adayların 1s mumlarında taban + hacim kıvılcımı arar, `sinyaller.csv`'ye ekler, Telegram mesajı üretir
- `degerlendir.py` – sinyallerden sonraki 7 günü ölçer (%10+ sıçradı mı)
- `sinyaller.csv` – tüm sinyallerin kaydı (silmeyin; temizle.sh bu klasöre dokunmaz)
