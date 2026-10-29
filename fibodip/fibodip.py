"""
FiboDip – hacimli dip taraması (BIST)

Kullanım:
  python3 fibodip.py <screener_dosyasi.json> [--son-tarih YYYY-MM-DD] [--durum son_gonderim.txt] [--mesaj mesaj.txt] [--json adaylar.json]

Kurallar (her şey screener verisinden, uydurma yok):
  konum      = (kapanış - 3A dip) / (3A tepe - 3A dip)      -> 0 = 3 aylık dip, 1 = 3 aylık tepe
  dip bandı  = 0.114 <= konum <= 0.382   (0.114 altı = hâlâ dibe yapışık / düşen bıçak, alınmaz)
  hacim şartı= son gün hacmi >= 1.5 x 30 günlük ortalama hacim
  likidite   = 30 günlük ortalama ciro >= 10 milyon TL
Seviyeler (bilgi amaçlı, kurala dayalı):
  giriş  = son kapanış
  stop   = 3 aylık dibin %2 altı
  hedef1 = 3 aylık aralığın 0.5 seviyesi, hedef2 = 0.618 seviyesi

Screener sütunları: name, close, change, High.3M, Low.3M, volume, average_volume_30d_calc,
                    AvgValue.Traded_30d, RSI, Perf.3M, sector, EMA50, EMA200
Çıktı: mesaj dosyası (Telegram HTML) + adaylar JSON (yorum yazmak için).
Durum dosyası verilirse ve --son-tarih zaten oradaysa "TEKRAR" yazar ve çıkar (tatil günü tekrar gönderimi önler).
"""
import json, sys, argparse

KONUM_MIN, KONUM_MAX, HACIM_KAT, CIRO_MIN = 0.114, 0.382, 1.5, 10e6
BANTLAR = [(0.114, 0.236, "0.114–0.236"), (0.236, 0.382, "0.236–0.382")]

ap = argparse.ArgumentParser()
ap.add_argument("screener")
ap.add_argument("--son-tarih", default="")
ap.add_argument("--durum", default="")
ap.add_argument("--mesaj", default="mesaj.txt")
ap.add_argument("--json", default="adaylar.json")
a = ap.parse_args()

if a.durum and a.son_tarih:
    try:
        if open(a.durum).read().strip() == a.son_tarih:
            print("TEKRAR: bu işlem günü için liste zaten gönderilmiş"); sys.exit(0)
    except FileNotFoundError:
        pass

raw = json.load(open(a.screener))
rows = raw["data"]["rows"] if "data" in raw else raw["rows"]

def f(x):
    try: return float(x)
    except (TypeError, ValueError): return None

toplam, dipte, aday = len(rows), 0, []
for r in rows:
    c, hi, lo = f(r.get("close")), f(r.get("High.3M")), f(r.get("Low.3M"))
    v, av, ciro = f(r.get("volume")), f(r.get("average_volume_30d_calc")), f(r.get("AvgValue.Traded_30d"))
    if None in (c, hi, lo) or hi <= lo:
        continue
    k = (c - lo) / (hi - lo)
    if not (KONUM_MIN <= k <= KONUM_MAX):
        continue
    if ciro is None or ciro < CIRO_MIN:
        continue
    dipte += 1
    if not v or not av or v / av < HACIM_KAT:
        continue
    bant = next(b[2] for b in BANTLAR if b[0] <= k <= b[1])
    stop = lo * 0.98
    h1, h2 = lo + 0.5 * (hi - lo), lo + 0.618 * (hi - lo)
    ema50, ema200 = f(r.get("EMA50")), f(r.get("EMA200"))
    aday.append(dict(
        hisse=r["name"], kapanis=c, degisim=f(r.get("change")), konum=round(k, 3), bant=bant,
        hacim_kat=round(v / av, 2), ciro30_mn=round(ciro / 1e6, 1), rsi=f(r.get("RSI")),
        perf3a=f(r.get("Perf.3M")), sektor=r.get("sector"),
        ema50_uzaklik=round((c / ema50 - 1) * 100, 1) if ema50 else None,
        ema200_uzaklik=round((c / ema200 - 1) * 100, 1) if ema200 else None,
        tepe3a=hi, dip3a=lo, giris=c, stop=round(stop, 2), stop_pct=round((stop / c - 1) * 100, 1),
        hedef1=round(h1, 2), hedef1_pct=round((h1 / c - 1) * 100, 1),
        hedef2=round(h2, 2), hedef2_pct=round((h2 / c - 1) * 100, 1)))

aday.sort(key=lambda x: x["konum"])
json.dump(dict(tarih=a.son_tarih, toplam=toplam, dip_bandinda=dipte, adaylar=aday),
          open(a.json, "w"), ensure_ascii=False, indent=1)

fmt = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
L = [f"<b>FiboDip · hacimli dip taraması</b> ({a.son_tarih or 'son işlem günü'} kapanışı)",
     f"Likit {dipte} hisse dip bandında (konum 0,114–0,382); hacim ≥ 1,5x şartını geçen: <b>{len(aday)}</b>", ""]
if not aday:
    L.append("Bugün şartları sağlayan hisse yok.")
else:
    L.append("<pre>Hisse   Kapanış  Konum  Hacim  Stop%  H1%")
    for x in aday:
        L.append(f"{x['hisse']:<7}{fmt(x['kapanis']):>8}  {x['konum']:.3f}  x{x['hacim_kat']:<4.2f} {x['stop_pct']:>5.1f} {x['hedef1_pct']:>5.1f}")
    L.append("</pre>")
open(a.mesaj, "w").write("\n".join(L))
print(f"TOPLAM={toplam} DIP_BANDINDA={dipte} ADAY={len(aday)}")
print("ADAYLAR=" + ",".join(x["hisse"] for x in aday))
