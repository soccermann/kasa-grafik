"""SVTI 15dk 43 — gün sonu raporu (TradingView 'SVTI NET v3.1' kuralının birebir Python karşılığı).

KURAL (15dk):
  AL : SVTI 0'ı yukarı keser + yeşil mum (kapanış > açılış) + hacim >= 20 bar ort. x1,5
       + XU100 15dk SVTI > 0   (ortalama mevcut barı da içerir, Pine ta.sma gibi)
  SAT: kapanış < ATR(14, RMA) x 3 iz süren stop (stop sadece yukarı gider)
  Giriş/çıkış bar kapanışında. Komisyon %0,1 gidiş-dönüş.
  5DK ONAYI (v2): her 15dk AL, son 30 dakika içinde aynı kuralla 5dk'da AL gelmişse "onay5=1" işaretlenir.
  Tüm 15dk AL'ler takip edilir; raporda hem tümü hem 5dk onaylılar ayrı istatistiklenir.
  GİRDİ VERİSİ 5 DAKİKALIKTIR; 15dk barları betik kendisi oluşturur (10:00'dan itibaren 15'er dk, açılış seansı ayrı bar).

KULLANIM:
  python3 svti15.py --bugun YYYY-MM-DD --xu <XU100_15m_dosyası> --bar SEMBOL=<dosya> [--bar ...]
                    --islemler islemler.csv --acik acik.json --mesaj /home/claude/mesaj.txt
  Dosyalar mcp-tv-get-ohlcv (interval 5m, count 5000, format columns) çıktısının kaydedildiği dosyalardır.
  islemler.csv: BASLANGIC (2026-11-06) ve sonrası girişli KAPANMIŞ işlemler (tekrar etmez, birleşir).
  Çıktının son satırı: OZET=... ; bugün seans yoksa "TATIL" basar ve mesaj yazmaz.
"""
import json,sys,argparse,csv,os,datetime as dt
BASLANGIC="2026-11-06"; VOLK=1.5; ATRM=3.0; COST=0.001
TZ=dt.timedelta(hours=3)
def load(p):
    d=json.loads(open(p).read())
    if isinstance(d,list): d=json.loads(d[0]["text"])
    return d["bars"] if "bars" in d else d
def tstr(t): return (dt.datetime.fromtimestamp(t,dt.timezone.utc)+TZ).strftime("%Y-%m-%d %H:%M")
def agg(D,mins):
    out={k:[] for k in "tohlcv"}; cur=None
    for i in range(len(D["c"])):
        tt=dt.datetime.fromtimestamp(D["t"][i],dt.timezone.utc)+TZ
        m=tt.hour*60+tt.minute-600; key=(tt.date(), m//mins if m>=0 else -1)
        if key!=cur:
            cur=key
            for k in "tohlc": out[k].append(D[k][i])
            out["v"].append(D["v"][i] or 0)
        else:
            out["h"][-1]=max(out["h"][-1],D["h"][i]); out["l"][-1]=min(out["l"][-1],D["l"][i]); out["c"][-1]=D["c"][i]; out["v"][-1]+=D["v"][i] or 0
    return out
def buys5(D):
    """5dk kuralı (XU filtresiz): AL barlarının bitiş zamanları"""
    t,o,h,l,c=D["t"],D["o"],D["h"],D["l"],D["c"]; v=[x or 0 for x in D["v"]]; n=len(c); s=svti(c)
    atr=[None]*n; a=None
    for i in range(1,n):
        tr=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])); a=tr if a is None else (a*13+tr)/14; atr[i]=a
    ip=False; out=[]
    for i in range(30,n):
        va=sum(v[i-19:i+1])/20
        if ip:
            if c[i]<trl: ip=False
            else: trl=max(trl,c[i]-atr[i]*ATRM)
        if not ip and s[i-1]<=0<s[i] and c[i]>o[i] and va>0 and v[i]>va*VOLK:
            ip=True; trl=c[i]-atr[i]*ATRM; out.append(t[i]+300)
    return out
def svti(c):
    n=len(c); raw=[None]*n; s=[None]*n
    for i in range(14,n): raw[i]=(c[i]-c[i-14])*0.6+(c[i]-c[i-8])*1.4
    for i in range(16,n): s[i]=sum(raw[i-2:i+1])/3*1.8
    return s
def sim(D,XUS,B5=()):
    t,o,h,l,c=D["t"],D["o"],D["h"],D["l"],D["c"]; v=[x or 0 for x in D["v"]]; n=len(c); s=svti(c)
    atr=[None]*n; a=None
    for i in range(1,n):
        tr=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])); a=tr if a is None else (a*13+tr)/14; atr[i]=a
    ip=False; trades=[]; cur=None
    for i in range(30,n):
        vavg=sum(v[i-19:i+1])/20
        if ip:
            if c[i]<trl:
                cur.update(cikis=tstr(t[i]),cikis_fiyat=c[i],getiri=round((c[i]/cur["giris_fiyat"]-1-COST)*100,2)); trades.append(cur); ip=False
            else: trl=max(trl,c[i]-atr[i]*ATRM)
        x=XUS.get(t[i])
        if not ip and s[i-1] is not None and s[i-1]<=0<s[i] and c[i]>o[i] and vavg>0 and v[i]>vavg*VOLK and x is not None and x>0:
            ip=True; trl=c[i]-atr[i]*ATRM
            E=t[i]+900
            cur={"giris":tstr(t[i]),"giris_fiyat":c[i],"hacim_kat":round(v[i]/vavg,1),"onay5":int(any(E-1800<=b<=E for b in B5))}
    acik=None
    if ip: acik=dict(cur,stop=round(trl,2),son=c[-1],anlik=round((c[-1]/cur["giris_fiyat"]-1)*100,2))
    return trades,acik,s[-1],tstr(t[-1])[:10]
ap=argparse.ArgumentParser(); ap.add_argument("--bugun",required=True); ap.add_argument("--xu",required=True)
ap.add_argument("--bar",action="append",default=[]); ap.add_argument("--islemler",required=True); ap.add_argument("--acik",required=True); ap.add_argument("--mesaj",required=True); ap.add_argument("--baslangic",default=BASLANGIC)
A=ap.parse_args(); BASLANGIC=A.baslangic
XU=agg(load(A.xu),15); xs=svti(XU["c"]); XUS=dict(zip(XU["t"],xs))
if tstr(XU["t"][-1])[:10]!=A.bugun: print("TATIL"); sys.exit(0)
xu_son=xs[-1]
bugun_al=[];bugun_sat=[];aciklar=[];kapananlar=[];eksik=[]
for b in A.bar:
    sym,p=b.split("=",1)
    try: D5=load(p); D=agg(D5,15); B5=buys5(D5)
    except Exception: eksik.append(sym); continue
    tr,ac,sl,son=sim(D,XUS,B5)
    if son!=A.bugun: eksik.append(sym)
    for x in tr:
        x["sembol"]=sym
        if x["giris"][:10]>=BASLANGIC: kapananlar.append(x)
        if x["giris"][:10]==A.bugun: bugun_al.append(x)
        if x["cikis"][:10]==A.bugun: bugun_sat.append(x)
    if ac:
        ac["sembol"]=sym; aciklar.append(ac)
        if ac["giris"][:10]==A.bugun: bugun_al.append(ac)
# kalıcı kayıt
F=["sembol","giris","giris_fiyat","hacim_kat","onay5","cikis","cikis_fiyat","getiri"]
eski={}
if os.path.exists(A.islemler):
    for r in csv.DictReader(open(A.islemler,encoding="utf-8")): r.setdefault("onay5",""); eski[(r["sembol"],r["giris"])]=r
for x in kapananlar: eski[(x["sembol"],x["giris"])]={k:x.get(k,"") for k in F}
rows=sorted(eski.values(),key=lambda r:(r["cikis"],r["sembol"]))
with open(A.islemler,"w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=F); w.writeheader(); w.writerows(rows)
json.dump({"tarih":A.bugun,"acik":aciklar},open(A.acik,"w"),ensure_ascii=False,indent=1)
# mesaj
ay=["","Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"]
y,m,d=A.bugun.split("-"); g=f"{int(d)} {ay[int(m)]}"
def e(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
L=[f"<b>SVTI 15dk · 43 hisse · gün sonu · {g}</b>",
   f"XU100 15dk SVTI kapanış: <b>{xu_son:+.2f}</b> → {'AL serbest ✓' if xu_son>0 else 'AL engelli ✗'}",""]
L.append(f"<b>🟢 Bugün AL ({len(bugun_al)})</b>")
for x in sorted(bugun_al,key=lambda x:x["giris"]):
    L.append(f"{e(x['sembol'])} · {x['giris'][11:]} · {x['giris_fiyat']} · hacim x{x['hacim_kat']}" + (" · ✓5dk" if x.get('onay5') else "") + (f" → aynı gün çıktı {x['getiri']:+.2f}%" if 'getiri' in x else ""))
if not bugun_al: L.append("—")
L.append(""); L.append(f"<b>🔴 Bugün SAT / STOP ({len(bugun_sat)})</b>")
for x in sorted(bugun_sat,key=lambda x:x["cikis"]):
    L.append(f"{e(x['sembol'])} · {x['giris'][5:16].replace('-','.')} {x['giris_fiyat']} → {x['cikis'][11:]} {x['cikis_fiyat']} · <b>{x['getiri']:+.2f}%</b>" + (" · ✓5dk" if x.get('onay5') else ""))
if not bugun_sat: L.append("—")
L.append(""); L.append(f"<b>📌 Açık pozisyonlar ({len(aciklar)})</b>")
for x in sorted(aciklar,key=lambda x:-x["anlik"]):
    L.append(f"{e(x['sembol'])} · giriş {x['giris'][5:16].replace('-','.')} {x['giris_fiyat']} · stop {x['stop']} · son {x['son']} · <b>{x['anlik']:+.2f}%</b>" + (" · ✓5dk" if x.get('onay5') else ""))
if not aciklar: L.append("—")
def ist(rr,ad):
    gr=[float(r["getiri"]) for r in rr]
    if not gr: return f"{ad}: henüz kapanan işlem yok"
    kz=sum(1 for x in gr if x>0); gg=sum(x for x in gr if x>0); bb=-sum(x for x in gr if x<0)
    return f"{ad}: {len(gr)} işlem · kazanan %{100*kz/len(gr):.0f} · ort {sum(gr)/len(gr):+.2f}% · toplam {sum(gr):+.1f}%" + (f" · kâr faktörü {gg/bb:.2f}" if bb else "")
gr=[float(r["getiri"]) for r in rows]
L.append("")
L.append(f"<b>📊 Takip başından beri ({BASLANGIC} →)</b>")
L.append(ist(rows,"Tüm 15dk AL'ler"))
L.append(ist([r for r in rows if str(r.get("onay5"))=="1"],"✓5dk onaylı (son 30 dk'da 5dk AL)"))
L.append(ist([r for r in rows if str(r.get("onay5"))=="0"],"5dk onaysız"))
if eksik: L.append(f"Veri alınamayan / güncel olmayan: {e(', '.join(eksik))}")
L.append("")
L.append("<i>Kural (15dk): SVTI 0 yukarı kesişim + yeşil mum + hacim ≥ x1,5 + XU100 15dk SVTI &gt; 0 → AL; ATR(14)x3 iz süren stop → SAT. ✓5dk = son 30 dk içinde 5dk'da da AL geldi. Kağıt üzerinde takip, yatırım tavsiyesi değildir.</i>")
open(A.mesaj,"w",encoding="utf-8").write("\n".join(L))
print(f"OZET= AL:{len(bugun_al)} SAT:{len(bugun_sat)} ACIK:{len(aciklar)} KAPANAN_TOPLAM:{len(gr)} XU15:{xu_son:+.2f} EKSIK:{','.join(eksik) or '-'}")
