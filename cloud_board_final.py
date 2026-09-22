import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, time

WEB_PASSWORD = "88666666"
HK_TZ = timezone(timedelta(hours=8))

WATCHLIST = [
    ("DXYZ", "Destiny Tech100"), ("SMCI", "超微電腦"), ("PENG", "Penguin"), ("NBIS", "Nebius Group"),
    ("BE", "Bloom Energy"), ("BEZ", "2X Short BE"), ("MU", "美光科技"), ("MUU", "美光2X"),
    ("MUZ", "美光Bear"), ("SNDK", "SanDisk"), ("SOXX", "半導體ETF"), ("SOXL", "半導體3X"),
    ("CRCL", "Circle"), ("CRCG", "Circle2X"), ("CRCD", "Circle反2X"), ("UPRO", "標普3X"),
    ("TQQQ", "納指3X"), ("SQQQ", "納指3X空"), ("9868.HK", "小鵬-W"), ("XPEV", "小鵬ADR"),
    ("TSLA", "特斯拉"), ("SPY", "標普500"), ("QQQ", "納指QQQ"), ("LI", "理想"), ("NIO", "蔚來"),
    ("BABA", "阿里"), ("FUTU", "富途"), ("NVDA", "輝達"), ("AMD", "超微"), ("INTC", "英特爾"),
    ("AAPL", "蘋果"), ("GOOGL", "谷歌-A"), ("GOOG", "谷歌-C"), ("MSFT", "微軟"), ("AMZN", "亞馬遜"),
]

def rsi(series, period=14):
    try:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))
    except:
        return pd.Series([50]*len(series), index=series.index)

def get_history(ticker, period, interval, prepost):
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=period, interval=interval, prepost=prepost, auto_adjust=True)
        if df.empty:
            time.sleep(1.0)
            df = tk.history(period=period, interval=interval, prepost=prepost, auto_adjust=True)
        return df
    except:
        return pd.DataFrame()

def calc_ma(s, p):
    try:
        if len(s) < p: return 0
        return float(s.rolling(p).mean().iloc[-1])
    except:
        return 0

def calc_color(d_close, d20, d60, d240, h_close, h20, h60, h240):
    if d60==0 or h20==0: return "白"
    if d_close < d60 and h_close < h20 and h_close < h60: return "紅"
    if d_close < d20 and h_close < h20: return "藍"
    if d_close > d60 and h_close > h240 and h_close > h60 and h240>0: return "橙"
    if d_close > d60 and h_close > h60: return "綠"
    return "灰"

results=[]
for code,name in WATCHLIST:
    try:
        df_day = get_history(code,"1y","1d",False)
        if df_day.empty or len(df_day)<61:
            results.append({"code":code,"name":name,"today":"白","yesterday":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None,"err":True})
            time.sleep(1.2); continue
        df_60m = get_history(code,"60d","60m",True)
        if df_60m.empty:
            results.append({"code":code,"name":name,"today":"白","yesterday":"白","curr":float(df_day['Close'].iloc[-1]),"pct":0,"d20":calc_ma(df_day['Close'],20),"d60":calc_ma(df_day['Close'],60),"d240":calc_ma(df_day['Close'],240),"h20":0,"h60":0,"h240":0,"rsi14":None,"err":True})
            time.sleep(1.2); continue
        curr = float(df_60m['Close'].iloc[-1])
        prev = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else curr
        pct = (curr/prev-1)*100 if prev else 0
        d_close = float(df_day['Close'].iloc[-1])
        d20 = calc_ma(df_day['Close'],20); d60 = calc_ma(df_day['Close'],60); d240 = calc_ma(df_day['Close'],240)
        h20 = calc_ma(df_60m['Close'],20); h60 = calc_ma(df_60m['Close'],60); h240 = calc_ma(df_60m['Close'],240)
        h_close = curr
        today = calc_color(d_close, d20, d60, d240, h_close, h20, h60, h240)
        df_day_y = df_day.iloc[:-1]
        d_close_y = float(df_day_y['Close'].iloc[-1])
        d20_y = calc_ma(df_day_y['Close'],20); d60_y = calc_ma(df_day_y['Close'],60); d240_y = calc_ma(df_day_y['Close'],240)
        try:
            today_date = df_day.index[-1].date()
            df_60m_y = df_60m[df_60m.index.date < today_date]
            if df_60m_y.empty: df_60m_y = df_60m.iloc[:-7]
            h20_y = calc_ma(df_60m_y['Close'],20); h60_y = calc_ma(df_60m_y['Close'],60); h240_y = calc_ma(df_60m_y['Close'],240)
            h_close_y = float(df_60m_y['Close'].iloc[-1]) if len(df_60m_y)>0 else d_close_y
        except:
            h20_y=h60_y=h240_y=h_close_y=d_close_y
        yesterday = calc_color(d_close_y, d20_y, d60_y, d240_y, h_close_y, h20_y, h60_y, h240_y)
        rsi14 = float(rsi(df_day['Close'],14).iloc[-1]) if len(df_day)>=15 else None
        results.append({"code":code,"name":name,"today":today,"yesterday":yesterday,"curr":round(curr,2),"pct":round(pct,2),"d20":round(d20,2),"d60":round(d60,2),"d240":round(d240,2),"h20":round(h20,2),"h60":round(h60,2),"h240":round(h240,2),"rsi14":rsi14,"err":False})
        time.sleep(1.2)
    except:
        results.append({"code":code,"name":name,"today":"白","yesterday":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None,"err":True})

order={"白":-1,"灰":0,"紅":1,"藍":2,"綠":3,"橙":4}
results.sort(key=lambda x: order.get(x["today"],0), reverse=True)
hk_now = datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M:%S")
os.makedirs("docs", exist_ok=True)
with open("docs/data.json","w",encoding="utf-8") as f:
    json.dump({"update":hk_now+" 香港時間","results":results},f,ensure_ascii=False,indent=2)

def ma_span_label(label, val, curr):
    if val==0: return f"<span class='ma-item'><span class='ma-w'>{label}(--)</span></span>"
    cls = "ma-red" if val > curr else "ma-green" if val < curr else "ma-same"
    return f"<span class='ma-item'><span class='ma-w'>{label}</span><span class='{cls}'>({val:.0f})</span></span>"

cards=""
for r in results:
    is_white = r['today']=="白"
    pct_cls="pct-up" if r['pct']>=0 else "pct-down"
    sign="+" if r['pct']>=0 else ""
    curr_html=f"<span class='price'>${r['curr']}</span>" if r['curr']>0 else "<span class='price'>--</span>"
    pct_html=f"<span class='pct {pct_cls}'>{sign}{r['pct']:.2f}%</span>" if r['curr']>0 and not is_white else ("<span class='pct'>限流</span>" if is_white else "")
    dots=f"<span class='dots'><span class='dot {r['yesterday']}'></span><span class='arrow'>→</span><span class='dot {r['today']}'></span></span>"
    rsi_inline=""
    if r['rsi14'] is not None:
        if r['rsi14']>=70:
            rsi_inline=f"<span class='rsi-inline rsi-green'>RSI14({r['rsi14']:.0f})</span>"
        elif r['rsi14']<=30:
            rsi_inline=f"<span class='rsi-inline rsi-red'>RSI14({r['rsi14']:.0f})</span>"
    if is_white:
        d_row = f"<div class='ma-row'><span class='ma-w'>限流</span></div>"
        h_row = f"<div class='ma-row'><span class='ma-w'>時k含盤前後已確認</span></div>"
    else:
        d_row = f"<div class='ma-row'><span class='ma-w'>日k：</span>{ma_span_label('MA20', r['d20'], r['curr'])} {ma_span_label('MA60', r['d60'], r['curr'])} {ma_span_label('MA240', r['d240'], r['curr'])}</div>"
        h_row = f"<div class='ma-row'><span class='ma-w'>時k：</span>{ma_span_label('MA20', r['h20'], r['curr'])} {ma_span_label('MA60', r['h60'], r['curr'])} {ma_span_label('MA240', r['h240'], r['curr'])}</div>"
    cards+=f"""
<div class="card {r['today']}" data-code="{r['code'].lower()}" data-name="{r['name'].lower()} {r['code'].lower()}" data-ticker="{r['code']}">
  <div class="left">
    <div class="top"><b>{r['code']}</b> {r['name']} {dots} {rsi_inline}</div>
    <div class="mid">{curr_html} {pct_html}</div>
    <div class="ma-box">{d_row}{h_row}</div>
  </div>
  <div class="star" onclick="togglePin('{r['code']}')" title="點擊置頂">☆</div>
</div>"""

html=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MA看板 私有版</title>
<style>
*{{box-sizing:border-box}} body{{font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial;background:#0a0e14;color:#e6e6e6;padding:14px;margin:0}}
#lock{{position:fixed;inset:0;background:#0a0e14;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:9999}}
#lock input{{padding:14px 18px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:18px;text-align:center;margin:14px;width:240px}}
#lock button{{padding:12px 28px;border-radius:12px;border:none;background:#f59e0b;color:#000;font-weight:800;font-size:16px;cursor:pointer}}
.header{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:10px 0}} h1{{font-size:18px;margin:0}} .search{{flex:1;min-width:180px;max-width:300px;position:relative}} 
.search input{{width:100%;padding:10px 14px 10px 36px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:12px;outline:none}} .search input:focus{{border-color:#f59e0b}} .search .icon{{position:absolute;left:10px;top:50%;transform:translateY(-50%)}}
.sub{{color:#94a3b8;font-size:11px;margin-bottom:12px}}
.addRow{{display:flex;gap:8px;align-items:center;margin:0 0 12px;flex-wrap:wrap}} .addRow input{{flex:1;min-width:200px;max-width:400px;padding:10px 14px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:12px;outline:none}} .addRow input:focus{{border-color:#f59e0b}} .addbtn{{padding:10px 16px;border-radius:12px;border:none;background:#f59e0b;color:#000;font-weight:800;cursor:pointer;white-space:nowrap}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px;align-items:start}}
.pinned-section{{margin-bottom:14px}} .pinned-title{{font-size:13px;color:#fde68a;margin:0 0 8px;display:none}} .pinned-title.show{{display:block}}
.card{{border-radius:14px;padding:11px 13px;display:flex;justify-content:space-between;align-items:flex-start;gap:10px;min-height:110px;overflow:hidden;transition:all 0.2s;position:relative}} .card.hide{{display:none}}
.橙{{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000}} .綠{{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000}} .灰{{background:#1e293b;color:#cbd5e1;border:1px solid #2a3441}} .藍{{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff}} .紅{{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff}} .白{{background:#fff;color:#000;border:2px dashed #94a3b8}}
.star{{font-size:20px;cursor:pointer;user-select:none;line-height:1;padding:2px 4px;border-radius:6px;flex-shrink:0;transition:all 0.2s}} .star.pinned{{color:#f59e0b;text-shadow:0 0 8px rgba(245,158,11,0.8)}} .card.橙 .star, .card.綠 .star{{color:#000}} .card.橙 .star.pinned, .card.綠 .star.pinned{{color:#78350f}}
.left{{flex:1;min-width:0}} .top{{font-size:12px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}} .mid{{margin-top:6px;display:flex;gap:8px;align-items:center}}
.price{{color:#facc15;font-weight:900;font-size:15px;background:rgba(0,0,0,0.32);padding:2px 8px;border-radius:6px}} .白 .price{{background:#000;color:#fff}}
.pct{{font-size:11px;font-weight:800;padding:3px 8px;border-radius:6px;background:rgba(0,0,0,0.45);color:#fff}} .pct-up{{color:#4ade80}} .pct-down{{color:#f87171}}
.dots{{display:inline-flex;align-items:center;background:rgba(0,0,0,0.18);padding:2px 7px;border-radius:12px;gap:3px}} .dot{{width:9px;height:9px;border-radius:50%;display:inline-block;border:1px solid rgba(0,0,0,0.2)}} .dot.橙{{background:#ff8a00}} .dot.綠{{background:#00c853}} .dot.藍{{background:#2962ff}} .dot.紅{{background:#d50000}} .dot.灰{{background:#94a3b8}} .dot.白{{background:#fff;border:1px solid #000}} .arrow{{font-size:9px}}
.rsi-inline{{font-size:10px;font-weight:900;padding:2px 7px;border-radius:6px;border:1px solid transparent;background:rgba(168,85,247,0.18);color:#e9d5ff}} .rsi-inline.rsi-green{{border-color:#22c55e;background:rgba(34,197,94,0.15);color:#bbf7d0}} .rsi-inline.rsi-red{{border-color:#ef4444;background:rgba(239,68,68,0.15);color:#fecaca}}
.ma-box{{margin-top:6px;background:#000;border-radius:8px;padding:7px 9px;border:1px solid #111}} .ma-row{{font-size:11px;line-height:1.7;display:flex;flex-wrap:wrap;gap:6px;align-items:center}} .ma-w{{color:#ffffff;font-weight:600}} .ma-item{{white-space:nowrap}} .ma-green{{color:#4ade80;font-weight:900}} .ma-red{{color:#f87171;font-weight:900}} .ma-same{{color:#ffffff}}
.pill{{padding:5px 10px;border-radius:18px;background:#1e293b;font-size:11px;margin:3px;display:inline-block;border:1px solid #334155}} .rule-box{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px;margin:14px 0;font-size:11px;line-height:1.8}} .ver{{background:#78350f;color:#fde68a;border:1px solid #92400e;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:800}}
.custom{{border:2px solid #f59e0b !important}}
</style></head><body>
<div id="lock"><h2 style="margin:0 0 8px">🔒 私有看板</h2><div style="color:#94a3b8;font-size:13px">請輸入密碼</div><input id="pw" type="password" placeholder="請輸入密碼"/><button onclick="check()">進入</button></div>

<div class="header">
<h1>🚀 MA(20/60/240) 私有版 <span class="ver">V13</span></h1>
<div class="search"><span class="icon">🔍</span><input id="search" type="text" placeholder="搜索代號/名稱模糊" /></div>
</div>
<div class="addRow"><input id="addInput" type="text" placeholder="加股：輸入 PLTR / 0700 / 0700.HK / NVDA 回車 (支持模糊 0700→0700.HK)" /><button class="addbtn" onclick="addStock()">+ 加股</button><button class="addbtn" style="background:#1e293b;color:#fff;border:1px solid #334155" onclick="clearCustom()">清空自加</button><span style="font-size:11px;color:#94a3b8">自加<span id="customCount">0</span>隻 置頂<span id="pinCount">0</span>隻</span></div>

<div class="sub">更新: {hk_now} 香港時間 | 共<span id="count">{len(results)}</span>隻</div>

<div class="pinned-section"><div id="pinnedTitle" class="pinned-title">⭐ 置頂觀察</div><div id="pinnedGrid" class="grid"></div></div>

<div style="margin-bottom:8px">
<span class="pill">🟠橙 主升 {len([r for r in results if r['today']=='橙'])}隻</span>
<span class="pill">🟢綠 次強 {len([r for r in results if r['today']=='綠'])}隻</span>
<span class="pill">🔵藍 弱 {len([r for r in results if r['today']=='藍'])}隻</span>
<span class="pill">🔴紅 空頭 {len([r for r in results if r['today']=='紅'])}隻</span>
<span class="pill">⚪灰 震盪 {len([r for r in results if r['today']=='灰'])}隻</span>
<span class="pill" style="background:#fff;color:#000">⬜白 限流 {len([r for r in results if r['today']=='白'])}隻</span>
</div>

<div class="grid" id="grid">{cards}</div>
<div id="customGrid" class="grid" style="margin-top:12px"></div>

<div class="rule-box">
<b>技術指標MA(20，60，240)：</b><br>
🟠 股價日k站上MA60，時k站上MA60和MA240。<br>
🟢 股價日k站上MA60，時k站上MA60（時k未站上240MA）。<br>
🔵 股價日k跌穿MA20，時k跌穿MA20。<br>
🔴 股價日k跌穿MA60，時k跌穿MA20和MA60。<br>
⚪ 不符合以上條件。<br>
⬜ 白=限流<br>
⭐ 點右上角星星置頂
</div>

<script>
const REAL_PW="{WEB_PASSWORD}";
function check(){{const v=document.getElementById('pw').value;if(v===REAL_PW){{document.getElementById('lock').style.display='none';sessionStorage.setItem('ma_pw','ok');}}else{{alert('密碼錯誤');}}}}
if(sessionStorage.getItem('ma_pw')==='ok')document.getElementById('lock').style.display='none';
document.getElementById('pw').addEventListener('keydown',e=>{{if(e.key==='Enter')check();}});

// 置頂功能
let pinnedStocks = JSON.parse(localStorage.getItem('pinnedV13')||'[]');
function isPinned(ticker){{ return pinnedStocks.includes(ticker); }}
function togglePin(ticker){{
  if(isPinned(ticker)){{ pinnedStocks = pinnedStocks.filter(t=>t!==ticker); }}
  else{{ pinnedStocks.push(ticker); }}
  localStorage.setItem('pinnedV13', JSON.stringify(pinnedStocks));
  renderPins();
  updateStars();
}}
function renderPins(){{
  const pinnedGrid = document.getElementById('pinnedGrid');
  const pinnedTitle = document.getElementById('pinnedTitle');
  pinnedGrid.innerHTML='';
  let pinnedCards=[];
  document.querySelectorAll('#grid .card, #customGrid .card').forEach(card=>{{
    let t=card.getAttribute('data-ticker')||card.getAttribute('data-code');
    if(!t) return;
    t=t.toUpperCase();
    if(isPinned(t)) pinnedCards.push(card);
  }});
  // 自加的也要
  pinnedCards.forEach(c=>{{
    let clone=c.cloneNode(true);
    clone.querySelector('.star').setAttribute('onclick', `togglePin('${{c.getAttribute('data-ticker').toUpperCase()}}')`);
    pinnedGrid.appendChild(clone);
  }});
  if(pinnedCards.length>0) pinnedTitle.classList.add('show'); else pinnedTitle.classList.remove('show');
  document.getElementById('pinCount').innerText=pinnedCards.length;
}}
function updateStars(){{
  document.querySelectorAll('.card').forEach(card=>{{
    let t=(card.getAttribute('data-ticker')||card.getAttribute('data-code')||'').toUpperCase();
    let star=card.querySelector('.star');
    if(!star) return;
    if(isPinned(t)){{ star.innerText='★'; star.classList.add('pinned'); }}
    else{{ star.innerText='☆'; star.classList.remove('pinned'); }}
  }});
}}

// 搜索
const searchInput=document.getElementById('search');
function doSearch(q){{
  q=q.trim().toLowerCase();
  document.querySelectorAll('#grid .card, #customGrid .card, #pinnedGrid .card').forEach(card=>{{
    if(card.closest('#pinnedGrid')) return; // 置頂區不搜
    const code=card.getAttribute('data-code')||''; const name=card.getAttribute('data-name')||'';
    if(!q) card.classList.remove('hide'); else {{ if(code.includes(q)||name.includes(q)) card.classList.remove('hide'); else card.classList.add('hide'); }}
  }});
}}
searchInput.addEventListener('input', e=>doSearch(e.target.value));

// 自助加股 - 修復版 支持模糊 0700→0700.HK
let customStocks = JSON.parse(localStorage.getItem('customStocksV13')||'[]');
const customGrid=document.getElementById('customGrid');
function saveCustom(){{ localStorage.setItem('customStocksV13', JSON.stringify(customStocks)); document.getElementById('customCount').innerText=customStocks.length; document.getElementById('count').innerText = {len(results)} + customStocks.length; }}
function clearCustom(){{ if(!confirm('清空所有自加？')) return; customStocks=[]; saveCustom(); customGrid.innerHTML=''; renderPins(); }}
function normalizeTicker(input){{
  input=input.trim().toUpperCase();
  if(!input) return null;
  // 模糊：0700 -> 0700.HK, 9988 -> 9988.HK
  if(/^\\d{{3,4}}$/.test(input)){{ return input+'.HK'; }}
  if(/^\\d{{5}}$/.test(input)){{ return input+'.HK'; }}
  // 0700 已含 .HK 保留
  return input;
}}

function calcMa(arr,p){{ if(arr.length<p) return 0; let sum=0; for(let i=arr.length-p;i<arr.length;i++) sum+=arr[i]; return sum/p; }}
function calcColor(d_c,d20,d60,d240,h_c,h20,h60,h240){{ if(!d60||!h20) return "白"; if(d_c<d60 && h_c<h20 && h_c<h60) return "紅"; if(d_c<d20 && h_c<h20) return "藍"; if(d_c>d60 && h_c>h240 && h_c>h60 && h240>0) return "橙"; if(d_c>d60 && h_c>h60) return "綠"; return "灰"; }}
function rsiCalc(closes,period=14){{ if(closes.length<period+1) return null; let gains=0,losses=0; for(let i=1;i<=period;i++){{ let d=closes[closes.length-period-1+i]-closes[closes.length-period-2+i]; if(d>0) gains+=d; else losses+=-d; }} gains/=period; losses/=period; if(losses===0) return 100; return 100-(100/(1+gains/losses)); }}

async function fetchWithProxy(url){{
  const proxies=[
    (u)=>`https://corsproxy.io/?${{encodeURIComponent(u)}}`,
    (u)=>`https://api.allorigins.win/raw?url=${{encodeURIComponent(u)}}`,
    (u)=>`https://api.codetabs.com/v1/proxy?quest=${{encodeURIComponent(u)}}`
  ];
  // 先直連
  try{{ let r=await fetch(url); if(r.ok){{ let j=await r.json(); if(j.chart?.result) return j; }} }}catch(e){{}}
  // 代理輪詢
  for(let p of proxies){{
    try{{ let r=await fetch(p(url)); if(r.ok){{ let j=await r.json(); if(j.chart?.result) return j; }} }}catch(e){{ continue; }}
  }}
  throw new Error('Yahoo擋了');
}}

async function fetchYahoo(ticker, range, interval, includePrePost){{
  let url=`https://query1.finance.yahoo.com/v8/finance/chart/${{encodeURIComponent(ticker)}}?range=${{range}}&interval=${{interval}}&includePrePost=${{includePrePost}}`;
  return await fetchWithProxy(url);
}}

async function addStock(tickerInput){{
  let raw=(tickerInput||document.getElementById('addInput').value||'').trim();
  if(!raw) return;
  let ticker=normalizeTicker(raw);
  if(!ticker) return;
  // 支持模糊：0700 同時試 0700.HK
  let candidates=[ticker];
  if(/^\\d{{4}}\\.HK$/.test(ticker)){{ candidates.push(ticker.replace('.HK','')); }} // 也試不帶HK
  else if(!ticker.includes('.')){{ candidates.push(ticker+'.HK'); }} // 美股也試港股？主要為了0700
  // 去重
  candidates=[...new Set(candidates)];

  document.getElementById('addInput').value='';
  let cardId='custom-'+ticker.replace(/\\./g,'-');
  if(document.getElementById(cardId)){{ alert(ticker+' 已加過'); return; }}
  customGrid.insertAdjacentHTML('beforeend', `<div id="${{cardId}}" class="card 白 custom" data-code="${{ticker.toLowerCase()}}" data-name="${{ticker.toLowerCase()}}" data-ticker="${{ticker}}"><div class="left"><div class="top"><b>${{ticker}}</b> 載入中...</div><div class="mid"><span class="price">抓取Yahoo中...試 ${{candidates.join(', ')}}</span></div><div class="ma-box"><div class="ma-row"><span class="ma-w">時k含盤前後抓取中...</span></div></div></div><div class="star" onclick="togglePin('${{ticker}}')">☆</div></div>`);

  let success=false;
  for(let tryTicker of candidates){{
    try{{
      let dayData=await fetchYahoo(tryTicker,'1y','1d',false);
      let hourData=await fetchYahoo(tryTicker,'2mo','60m',true);
      let dayResult=dayData.chart?.result?.[0];
      let hourResult=hourData.chart?.result?.[0];
      if(!dayResult?.indicators?.quote?.[0]?.close) throw new Error('無數據');
      let dayCloses=dayResult.indicators.quote[0].close.filter(v=>v!=null);
      let hourCloses=hourResult?.indicators?.quote?.[0]?.close?.filter(v=>v!=null)||dayCloses.slice(-60);
      if(dayCloses.length<61) throw new Error('數據不足');
      let curr=hourCloses[hourCloses.length-1];
      let prev=dayCloses[dayCloses.length-2];
      let pct=((curr/prev-1)*100);
      let d20=calcMa(dayCloses,20), d60=calcMa(dayCloses,60), d240=calcMa(dayCloses,240);
      let h20=calcMa(hourCloses,20), h60=calcMa(hourCloses,60), h240=calcMa(hourCloses,240);
      let today=calcColor(dayCloses[dayCloses.length-1],d20,d60,d240,curr,h20,h60,h240);
      let dayClosesY=dayCloses.slice(0,-1);
      let d20y=calcMa(dayClosesY,20), d60y=calcMa(dayClosesY,60), d240y=calcMa(dayClosesY,240);
      let hourClosesY=hourCloses.slice(0,-7);
      let h20y=calcMa(hourClosesY,20), h60y=calcMa(hourClosesY,60), h240y=calcMa(hourClosesY,240);
      let yesterday=calcColor(dayClosesY[dayClosesY.length-1],d20y,d60y,d240y,hourClosesY[hourClosesY.length-1]||dayClosesY[dayClosesY.length-1],h20y,h60y,h240y);
      let rsi=rsiCalc(dayCloses,14);
      let name=dayResult.meta?.longName||dayResult.meta?.shortName||tryTicker;
      ticker=tryTicker; // 用成功的ticker
      if(!customStocks.find(s=>s.code===ticker)){{ customStocks.push({{code:ticker,name:name}}); saveCustom(); }}
      let sign=pct>=0?'+':''; let pctCls=pct>=0?'pct-up':'pct-down';
      let rsiHtml=''; if(rsi!==null){{ if(rsi>=70) rsiHtml=`<span class='rsi-inline rsi-green'>RSI14(${{rsi.toFixed(0)}})</span>`; else if(rsi<=30) rsiHtml=`<span class='rsi-inline rsi-red'>RSI14(${{rsi.toFixed(0)}})</span>`; }}
      let maHtml=(label,val)=>{{ if(!val) return `<span class='ma-item'><span class='ma-w'>${{label}}(--)</span></span>`; let cls=val>curr?'ma-red':'ma-green'; return `<span class='ma-item'><span class='ma-w'>${{label}}</span><span class='${{cls}}'>(${{val.toFixed(0)}})</span></span>`; }};
      let dRow=`<div class='ma-row'><span class='ma-w'>日k：</span>${{maHtml('MA20',d20)}} ${{maHtml('MA60',d60)}} ${{maHtml('MA240',d240)}}</div>`;
      let hRow=`<div class='ma-row'><span class='ma-w'>時k：</span>${{maHtml('MA20',h20)}} ${{maHtml('MA60',h60)}} ${{maHtml('MA240',h240)}}</div>`;
      document.getElementById(cardId).outerHTML=`
      <div class="card ${{today}} custom" id="${{cardId}}" data-code="${{ticker.toLowerCase()}}" data-name="${{name.toLowerCase()}} ${{ticker.toLowerCase()}}" data-ticker="${{ticker}}" data-custom="1">
        <div class="left"><div class="top"><b>${{ticker}}</b> ${{name}} <span class="dots"><span class="dot ${{yesterday}}"></span><span class="arrow">→</span><span class="dot ${{today}}"></span></span> ${{rsiHtml}} <span style="font-size:10px;cursor:pointer" onclick="removeCustom('${{ticker}}')">❌</span></div><div class="mid"><span class="price">$${{curr.toFixed(2)}}</span> <span class="pct ${{pctCls}}">${{sign}}${{pct.toFixed(2)}}%</span></div><div class="ma-box">${{dRow}}${{hRow}}</div></div><div class="star ${{isPinned(ticker)?'pinned':''}}" onclick="togglePin('${{ticker}}')">${{isPinned(ticker)?'★':'☆'}}</div>
      </div>`;
      success=true; break;
    }}catch(e){{ console.warn(tryTicker+' 失敗', e.message); continue; }}
  }}
  if(!success){{
    document.getElementById(cardId).outerHTML=`<div class="card 白 custom" id="${{cardId}}" data-code="${{ticker.toLowerCase()}}" data-name="${{ticker.toLowerCase()}}" data-ticker="${{ticker}}"><div class="left"><div class="top"><b>${{ticker}}</b> 抓取失敗 <span style="font-size:10px;cursor:pointer" onclick="removeCustom('${{ticker}}')">❌</span></div><div class="mid"><span class="price">Yahoo暫時擋了，請稍後重試或試 ${{candidates.join('/')}}</span></div><div class="ma-box"><div class="ma-row"><span class="ma-w">提示：美股直接輸代號如 PLTR，港股輸 0700 會自動試 0700.HK</span></div></div></div><div class="star" onclick="togglePin('${{ticker}}')">☆</div></div>`;
  }}
  renderPins(); updateStars();
}}

function removeCustom(ticker){{ customStocks=customStocks.filter(s=>s.code!==ticker); pinnedStocks=pinnedStocks.filter(s=>s!==ticker); localStorage.setItem('pinnedV13',JSON.stringify(pinnedStocks)); saveCustom(); let el=document.getElementById('custom-'+ticker.replace(/\\./g,'-')); if(el) el.remove(); renderPins(); }}

document.getElementById('addInput').addEventListener('keydown', e=>{{ if(e.key==='Enter') addStock(); }});

(async ()=>{{ 
  saveCustom(); 
  for(let s of customStocks){{ await addStock(s.code); await new Promise(r=>setTimeout(r,900)); }}
  renderPins(); updateStars();
}})();
</script>
</body></html>
"""
with open("docs/index.html","w",encoding="utf-8") as f:
    f.write(html)
print("V13 置頂星星 + 加股修復 + 模糊支持 + 版面精簡 已生成")
