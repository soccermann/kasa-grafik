"""tracker_log.json -> report.html (haftalik kagit takip sayfasi)."""
import json
import sys
import html

LABEL = {'DUSUKVOL_90': 'Düşük oynaklık + BTC filtresi',
         'MOMMA_30': 'Momentum + trend + BTC filtresi'}
TUM_LABEL = {'TUM_DUSUKVOL': 'Tüm Binance · Düşük oynaklık',
             'TUM_MOMMA': 'Tüm Binance · Momentum + trend'}
SHORT = {'DUSUKVOL_90': 'Düşük oynaklık', 'MOMMA_30': 'Momentum + trend',
         'TUM_DUSUKVOL': 'Tüm · Düşük oynaklık', 'TUM_MOMMA': 'Tüm · Momentum',
         'btc': 'BTC al-tut', 'esit_agirlik': 'Tüm coinler eşit'}
COLORS = {'DUSUKVOL_90': 'var(--calm)', 'MOMMA_30': 'var(--mom)',
          'TUM_DUSUKVOL': 'var(--calm)', 'TUM_MOMMA': 'var(--mom)',
          'btc': 'var(--btc)', 'esit_agirlik': 'var(--muted)'}
TR_MONTH = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz',
            'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']


def d_tr(s):
    y, m, d = s.split('-')
    return f"{int(d)} {TR_MONTH[int(m) - 1]} {y}"


def pct(x, signed=True):
    if x is None:
        return '<span class="dim">–</span>'
    cls = 'pos' if x > 0 else 'neg' if x < 0 else ''
    s = f"{x:+.1f}%" if signed else f"{x:.1f}%"
    return f'<span class="{cls}">{s.replace(".", ",")}</span>'


def price(p):
    if p >= 1000:
        s = f"{p:,.0f}".replace(',', '.')
    elif p >= 1:
        s = f"{p:.3f}".replace('.', ',')
    else:
        s = f"{p:.5f}".replace('.', ',')
    return s


def picks_table(picks, vol_label='Oynaklık', vol_signed=False):
    rows = ''.join(
        f"<tr><th scope='row'>{html.escape(p.get('binance', p['coin']))}</th><td>{price(p['entry'])}</td>"
        f"<td>{pct(p['ret_7g'])}</td><td>{pct(p['ret_30g'])}</td><td>{pct(p['btc_gore_30g'])}</td>"
        f"<td>{pct(p['oynaklik_30g'], False)}</td><td>{pct(p['ma50_uzaklik'])}</td>"
        f"<td>{last_col(p)}</td></tr>" for p in picks)
    last_h = 'Hacim 7/30' if picks and picks[0].get('hacim_7_30') is not None else 'Binance hacmi'
    return ("<div class='scroll'><table><thead><tr><th>Coin</th><th>Giriş</th><th>7 gün</th>"
            f"<th>30 gün</th><th>BTC'ye göre</th><th>{vol_label}</th><th>MA50'ye uzaklık</th>"
            f"<th>{last_h}</th></tr></thead><tbody>{rows}</tbody></table></div>")


def last_col(p):
    if p.get('hacim_7_30') is not None:
        return f"{str(p['hacim_7_30']).replace('.', ',')}x"
    if p.get('binance_dv_musd') is not None:
        return f"{str(p['binance_dv_musd']).replace('.', ',')} M$"
    return '–'


def line_chart(rows, keys=('DUSUKVOL_90', 'MOMMA_30', 'btc', 'esit_agirlik')):
    series = {k: [100.0] for k in keys}
    for r in rows:
        for k in keys:
            v = r.get(k) or 0
            series[k].append(series[k][-1] * (1 + v / 100))
    allv = [v for s in series.values() for v in s]
    lo, hi = min(allv), max(allv)
    pad = max((hi - lo) * 0.12, 2)
    lo, hi = lo - pad, hi + pad
    W, H, L, R, T, B = 640, 260, 52, 120, 16, 34
    n = len(rows)
    x = lambda i: L + (W - L - R) * (i / max(n, 1))
    y = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo))
    grid = ''
    step = max(1, round((hi - lo) / 4))
    g = int(lo // step + 1) * step
    while g < hi:
        grid += (f"<line x1='{L}' x2='{W - R}' y1='{y(g):.1f}' y2='{y(g):.1f}' class='grid'/>"
                 f"<text x='{L - 8}' y='{y(g) + 4:.1f}' text-anchor='end' class='tick'>{g:g}</text>")
        g += step
    dates = [rows[0]['from']] + [r['to'] for r in rows]
    xl = ''.join(f"<text x='{x(i):.1f}' y='{H - 10}' text-anchor='middle' class='tick'>"
                 f"{d[8:]}.{d[5:7]}</text>" for i, d in enumerate(dates))
    lines, labels, used = '', '', []
    for k in keys:
        pts = ' '.join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(series[k]))
        lines += f"<polyline points='{pts}' fill='none' stroke='{COLORS[k]}' stroke-width='{2.5 if k in LABEL or k in TUM_LABEL else 1.6}'/>"
        ly = y(series[k][-1])
        while any(abs(ly - u) < 14 for u in used):
            ly += 14
        used.append(ly)
        lines += f"<circle cx='{x(n):.1f}' cy='{y(series[k][-1]):.1f}' r='3.5' fill='{COLORS[k]}'/>"
        labels += (f"<text x='{x(n) + 10:.1f}' y='{ly + 4:.1f}' class='lab' fill='{COLORS[k]}'>"
                   f"{SHORT[k]} {series[k][-1]:.1f}</text>")
    return (f"<div class='scroll'><svg viewBox='0 0 {W} {H}' role='img' "
            f"aria-label='100 ile başlayan kağıt portföy değerleri'>{grid}{xl}{lines}{labels}</svg></div>")


def tum_section(tl):
    w = tl['weeks'][-1]
    s = tl['summary']
    lists = ''.join(
        f"<section class='list'><h3><i style='background:{COLORS[k]}'></i>{TUM_LABEL[k]}</h3>"
        f"{picks_table(w['picks'][k], 'ATR (14 gün)')}</section>" for k in TUM_LABEL)
    if s['rows']:
        cum = s['cumulative_pct']
        keys = ['TUM_DUSUKVOL', 'TUM_MOMMA', 'btc', 'esit_agirlik']
        tiles = ''.join(f"<div class='tile'><span>{SHORT[k]}</span><b>{pct(cum[k])}</b></div>" for k in keys)
        wk = ''.join(
            f"<tr><th scope='row'>{d_tr(r['from'])}</th><td>{'Piyasada' if r['in_market'] else 'Nakit'}</td>"
            f"<td>{pct(r['TUM_DUSUKVOL'])}</td><td>{pct(r['TUM_MOMMA'])}</td><td>{pct(r['btc'])}</td>"
            f"<td>{pct(r['esit_agirlik'])}</td></tr>" for r in reversed(s['rows']))
        res = (f"<div class='tiles'>{tiles}</div>{line_chart(s['rows'], keys)}"
               "<div class='scroll'><table><thead><tr><th>Hafta başı</th><th>BTC filtresi</th><th>Tüm · Düşük oynaklık</th>"
               f"<th>Tüm · Momentum</th><th>BTC</th><th>Tüm coinler</th></tr></thead><tbody>{wk}</tbody></table></div>")
    else:
        res = "<p class='empty'>İlk sonuç bir hafta sonra.</p>"
    return (f"<section><h2>Tüm Binance (deneysel)</h2>"
            f"<p>Aynı iki kural, Binance'te işlem gören ve 30 günlük Binance hacmi günde 1 milyon doları geçen bütün coinlere "
            f"uygulanır. Bu hafta {w.get('n_eligible', len(w['eligible']))} coin tarandı. Bu sürüm geçmişte test edilmedi; "
            f"44 coinlik sürümle karşılaştırmak için izleniyor.</p><div class='lists'>{lists}</div>{res}"
            "<p class='note'>Farklar: oynaklık 90 günlük sapma yerine 14 günlük ATR ile ölçülür; fiyatlar pazar akşamı tarama "
            "anındaki fiyattır; stablecoin, sarılı token, staking tokenı, altın ve tokenize hisse/ETF tokenları dışarıda tutulur.</p></section>")


def build(log, tum=None):
    w = log['weeks'][-1]
    s = log['summary']
    rows = s['rows']
    filt = (f"<span class='pill on'>Piyasada</span> BTC {price(w['btc_close'])}, 50 günlük ortalama "
            f"{price(w['btc_ma50'])}" if w['in_market'] else
            f"<span class='pill off'>Nakitte</span> BTC {price(w['btc_close'])}, 50 günlük ortalamanın "
            f"({price(w['btc_ma50'])}) altında. Bu hafta iki liste de alım yapmaz; adaylar sadece not edilir.")
    both = set(p['coin'] for p in w['picks']['DUSUKVOL_90']) & set(p['coin'] for p in w['picks']['MOMMA_30'])
    lists = ''.join(
        f"<section class='list'><h3><i style='background:{COLORS[k]}'></i>{LABEL[k]}</h3>{picks_table(w['picks'][k])}</section>"
        for k in LABEL)
    if rows:
        cum = s['cumulative_pct']
        tiles = ''.join(f"<div class='tile'><span>{SHORT[k]}</span><b>{pct(cum[k])}</b></div>"
                        for k in ['DUSUKVOL_90', 'MOMMA_30', 'btc', 'esit_agirlik'])
        wk = ''.join(
            f"<tr><th scope='row'>{d_tr(r['from'])}</th><td>{'Piyasada' if r['in_market'] else 'Nakit'}</td>"
            f"<td>{pct(r['DUSUKVOL_90'])}</td><td>{pct(r['MOMMA_30'])}</td><td>{pct(r['btc'])}</td>"
            f"<td>{pct(r['esit_agirlik'])}</td></tr>" for r in reversed(rows))
        last = [p for p in s['picks_eval'] if p['week'] == rows[-1]['from']]
        lastp = ''.join(f"<tr><th scope='row'>{p['coin']}</th><td>{SHORT[p['list']]}</td><td>{pct(p['ret'])}</td></tr>"
                        for p in sorted(last, key=lambda p: -p['ret']))
        results = (f"<div class='tiles'>{tiles}</div>{line_chart(rows)}"
                   "<h3>Hafta hafta</h3><div class='scroll'><table><thead><tr><th>Hafta başı</th><th>BTC filtresi</th>"
                   "<th>Düşük oynaklık</th><th>Momentum + trend</th><th>BTC</th><th>Tüm coinler</th></tr></thead>"
                   f"<tbody>{wk}</tbody></table></div>"
                   f"<h3>Geçen haftanın coinleri ({d_tr(rows[-1]['from'])} → {d_tr(rows[-1]['to'])})</h3>"
                   "<div class='scroll'><table class='narrow'><thead><tr><th>Coin</th><th>Liste</th><th>Getiri</th></tr></thead>"
                   f"<tbody>{lastp}</tbody></table></div>")
    else:
        results = ("<p class='empty'>İlk sonuçlar bir hafta sonra gelecek. Bu haftanın adayları kayda alındı; "
                   "gelecek pazar giriş fiyatlarıyla karşılaştırılacak.</p>")
    t = s.get('traits') or {}
    if s['weeks_done'] >= 3 and t:
        names = {'ret_7g': '7 günlük getiri', 'ret_30g': '30 günlük getiri', 'btc_gore_30g': "BTC'ye göre 30 gün",
                 'oynaklik_30g': 'Oynaklık', 'ma50_uzaklik': "MA50'ye uzaklık", 'hacim_7_30': 'Hacim 7/30'}
        tr_rows = ''.join(f"<tr><th scope='row'>{names[f]}</th><td>{t['kazanan_medyan'].get(f, '–')}</td>"
                          f"<td>{t['kaybeden_medyan'].get(f, '–')}</td></tr>" for f in names)
        traits = (f"<p>{t['n_picks']} seçimin %{str(t['win_rate_pct']).replace('.', ',')} kadarı haftayı artıda kapattı. "
                  "Kazananlar ile kaybedenlerin seçildikleri günkü ortanca değerleri:</p>"
                  "<div class='scroll'><table class='narrow'><thead><tr><th>Özellik</th><th>Kazananlar</th><th>Kaybedenler</th>"
                  f"</tr></thead><tbody>{tr_rows}</tbody></table></div>"
                  "<p class='note'>Birkaç haftalık veri tesadüfe çok açık. Bir fark ancak haftalar boyunca aynı yönde "
                  "tekrar ederse kural adayı sayılır; o zaman da önce 3 kapıdan geçirilir.</p>")
    else:
        traits = (f"<p class='empty'>Kazanan ve kaybeden coinlerin ortak özellikleri en az 3 hafta dolunca burada çıkacak. "
                  f"Şu an tamamlanan hafta: {s['weeks_done']}.</p>")
    common = (f"Bu hafta iki listede ortak coin: <b>{', '.join(sorted(both))}</b>." if both
              else "Bu hafta iki listede ortak coin yok.")
    css = open(__file__.replace('report.py', 'report.css')).read() if False else CSS
    return f"""<title>Coin Takip Defteri</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<main>
<header>
<p class="eyebrow">Kağıt takip · Binance spot · haftalık</p>
<h1>Coin Takip Defteri</h1>
<p class="lede">{d_tr(w['date'])} kapanışına göre. Takip başlangıcı: {d_tr(log['start'])}. Gerçek para yok; amaç iki taramanın birkaç hafta içinde nasıl davrandığını görmek.</p>
<p class="filter">{filt}</p>
</header>
<section><h2>Bu haftanın seçimleri</h2><p>{common}</p><div class="lists">{lists}</div></section>
<section><h2>Sonuçlar</h2>{results}</section>
<section><h2>Ortak özellikler</h2>{traits}</section>
{tum_section(tum) if tum else ''}
<section class="method"><h2>Kurallar</h2>
<ul>
<li>Her pazar, bir önceki günün kapanışına göre 44 Binance USDT coini taranır. 60 günden kısa geçmişi olanlar ve 30 günlük ortalama işlem hacmi 1 milyon doların altında kalanlar elenir.</li>
<li>Düşük oynaklık: son 90 günde fiyatı en az dalgalanan 5 coin. Momentum + trend: 50 günlük ortalamanın üstünde olup son 30 günde en çok yükselen 5 coin.</li>
<li>BTC 50 günlük ortalamanın altındaysa iki liste de nakitte bekler.</li>
<li>Giriş fiyatı sinyal günü kapanışıdır. Değişen her pozisyon için alış ve satış başına %0,08 maliyet düşülür.</li>
<li>Geçmiş testte bu iki tarama 3 kapının hepsinden geçmedi. Bu sayfa bir yatırım tavsiyesi değildir.</li>
</ul></section>
</main>"""


CSS = """
/* Defter düzeni: tek sütun, sayılar tablo olarak; iki liste yan yana, dar ekranda alt alta */
:root{--bg:#f3f5f4;--panel:#ffffff;--fg:#17201d;--muted:#5f6b67;--line:#d8dfdc;
--calm:#2f6f8f;--mom:#b4572a;--btc:#9a7b12;--pos:#1d7a4c;--neg:#b23a3a;
--display:'Bricolage Grotesque',ui-sans-serif,system-ui,sans-serif;
--body:'IBM Plex Sans',ui-sans-serif,system-ui,sans-serif;--mono:'IBM Plex Mono',ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111614;--panel:#18201d;--fg:#e4ebe8;--muted:#93a19c;--line:#2b3632;
--calm:#6fb2d4;--mom:#e88a5c;--btc:#d4b44a;--pos:#5cc48e;--neg:#ef7d7d;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#111614;--panel:#18201d;--fg:#e4ebe8;--muted:#93a19c;--line:#2b3632;
--calm:#6fb2d4;--mom:#e88a5c;--btc:#d4b44a;--pos:#5cc48e;--neg:#ef7d7d;color-scheme:dark}
body{background:var(--bg);color:var(--fg);font-family:var(--body);font-size:15px;line-height:1.55;
padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
main{max-width:980px;margin:0 auto;padding-block:32px 56px;display:grid;gap:40px}
header{display:grid;gap:10px}
.eyebrow{margin:0;font-family:var(--mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
h1{margin:0;font-family:var(--display);font-size:clamp(30px,5vw,44px);line-height:1.05;text-wrap:balance}
h2{margin:0 0 12px;font-family:var(--display);font-size:22px}
h3{margin:20px 0 8px;font-size:15px;font-weight:600;display:flex;align-items:center;gap:8px}
h3 i{width:10px;height:10px;border-radius:2px;display:inline-block}
p{margin:0 0 10px;max-width:68ch}
.lede{color:var(--muted)}
.filter{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.pill{font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;border:1px solid currentColor}
.pill.on{color:var(--pos)}.pill.off{color:var(--neg)}
.lists{display:grid;grid-template-columns:1fr;gap:8px}
.list{min-width:0}
.scroll{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums}
table.narrow{max-width:520px}
th,td{padding:8px 12px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--line)}
thead th{font-family:var(--body);font-weight:500;font-size:12px;color:var(--muted)}
th:first-child,td:first-child{text-align:left}
tbody th{font-weight:600}
tbody tr:last-child>*{border-bottom:0}
.pos{color:var(--pos)}.neg{color:var(--neg)}.dim{color:var(--muted)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px 14px;display:grid;gap:4px}
.tile span{font-size:12px;color:var(--muted)}.tile b{font-family:var(--mono);font-size:20px;font-weight:500}
svg{display:block;width:100%;min-width:520px;height:auto}
svg .grid{stroke:var(--line);stroke-width:1}
svg .tick{fill:var(--muted);font:11px var(--mono)}
svg .lab{font:600 12px var(--body)}
.empty{color:var(--muted);background:var(--panel);border:1px dashed var(--line);border-radius:6px;padding:14px 16px;max-width:none}
.note{font-size:13px;color:var(--muted)}
.method ul{margin:0;padding-left:18px;display:grid;gap:6px;max-width:72ch;color:var(--muted)}
"""

if __name__ == '__main__':
    log = json.load(open(sys.argv[1]))
    tum = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
    open(sys.argv[2], 'w').write(build(log, tum))
