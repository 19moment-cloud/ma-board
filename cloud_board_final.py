import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, time, traceback

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

results=[]
for code,name in WATCHLIST:
    try:
        df_day = get_history(code,"1y","1d",False)
        if df_day.empty or len(df_day)<20:
            results.append({"code":code,"name":name,"today":"白","yesterday":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None,"err":True})
            time.sleep(1.2); continue
        df_60m = get_history(code,"60d","60m",True)  # 時k含盤前後 prepost=True
        if df_60m.empty:
            results.append({"code":code,"name":name,"today":"白","yesterday":"白","curr":float(df_day['Close'].iloc[-1]),"pct":0,"d20":calc_ma(df_day['Close'],20),"d60":calc_ma(df_day['Close'],60),"d240":calc_ma(df_day['Close'],240),"h20":0,"h60":0,"h240":0,"rsi14":None,"err":True})
            time.sleep(1.2); continue
        curr = float(df_60m['Close'].iloc[-1]) if not df_60m.empty else float(df_day['Close'].iloc[-1])
        prev = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else curr
        pct = (curr/prev-1)*100 if prev else 0
        d_close = float(df_day['Close'].iloc[-1])
        d20 = calc_ma(df_day['Close'],20); d60 = calc_ma(df_day['Close'],60); d240 = calc_ma(df_day['Close'],240)
        h20 = calc_ma(df_60m['Close'],20); h60 = calc_ma(df_60m['Close'],60); h240 = calc_ma(df_60m['Close'],240)
        h_close = curr
        if d_close < d60 and h_close < h20 and h_close < h60: today="紅"
        elif d_close < d20 and h_close < h20: today="藍"
        elif d_close > d60 and h_close > h240 and h_close > h60 and h240>0: today="橙"
        elif d_close > d60 and h_close > h60: today="綠"
        else: today="灰"
        yesterday=today
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
    if val==0: return f"<span class='ma-item'><span class='ma-w'> {label}(--)</span></span>"
    cls = "ma-green" if val > curr else "ma-red" if val < curr else "ma-same"
    # 白色字部分：label 是白色，括號價是紅綠
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
        d_row = f"<div class='ma-row'><span class='ma-w'>限流未抓到，白=限流，灰=震盪</span></div>"
        h_row = f"<div class='ma-row'><span class='ma-w'>時k含盤前後 prepost=True 已確認</span></div>"
    else:
        d_row = f"<div class='ma-row'><span class='ma-w'>日k：</span>{ma_span_label('MA20', r['d20'], r['curr'])} {ma_span_label('MA60', r['d60'], r['curr'])} {ma_span_label('MA240', r['d240'], r['curr'])}</div>"
        h_row = f"<div class='ma-row'><span class='ma-w'>時k：</span>{ma_span_label('MA20', r['h20'], r['curr'])} {ma_span_label('MA60', r['h60'], r['curr'])} {ma_span_label('MA240', r['h240'], r['curr'])}</div>"

    cards+=f"""
<div class="card {r['today']}" data-code="{r['code'].lower()}" data-name="{r['name'].lower()} {r['code'].lower()}">
  <div class="left">
    <div class="top"><b>{r['code']}</b> {r['name']} {dots} {rsi_inline}</div>
    <div class="mid">{curr_html} {pct_html}</div>
    <div class="ma-box">{d_row}{h_row}</div>
  </div>
  <div class="badge">{r['today']}</div>
</div>"""

html=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MA看板 私有版</title>
<style>
*{{box-sizing:border-box}} body{{font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial;background:#0a0e14;color:#e6e6e6;padding:14px;margin:0}}
#lock{{position:fixed;inset:0;background:#0a0e14;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:9999}}
#lock input{{padding:14px 18px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:18px;text-align:center;margin:14px;width:240px}}
#lock button{{padding:12px 28px;border-radius:12px;border:none;background:#f59e0b;color:#000;font-weight:800;font-size:16px;cursor:pointer}}
.header{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:10px 0}} h1{{font-size:18px;margin:0}}
.search{{flex:1;min-width:220px;max-width:360px;position:relative}}
.search input{{width:100%;padding:10px 14px 10px 36px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:13px;outline:none}}
.search input:focus{{border-color:#f59e0b}} .search .icon{{position:absolute;left:10px;top:50%;transform:translateY(-50%);opacity:0.6}}
.sub{{color:#94a3b8;font-size:11px;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px;align-items:start}}
.card{{border-radius:14px;padding:11px 13px;display:flex;justify-content:space-between;align-items:flex-start;gap:10px;min-height:110px;overflow:hidden;transition:all 0.2s}}
.card.hide{{display:none}}
.橙{{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000}} .綠{{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000}}
.灰{{background:#1e293b;color:#cbd5e1;border:1px solid #2a3441}} .藍{{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff}} .紅{{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff}}
.白{{background:#ffffff;color:#000;border:2px dashed #94a3b8}}
.badge{{padding:5px 10px;border-radius:16px;font-weight:800;font-size:13px;background:rgba(0,0,0,0.18);min-width:26px;text-align:center;flex-shrink:0}} .白 .badge{{background:#000;color:#fff}}
.left{{flex:1;min-width:0}} .top{{font-size:12px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}} .mid{{margin-top:6px;display:flex;gap:8px;align-items:center}}
.price{{color:#facc15;font-weight:900;font-size:15px;background:rgba(0,0,0,0.32);padding:2px 8px;border-radius:6px}} .白 .price{{background:#000;color:#fff}}
.pct{{font-size:11px;font-weight:800;padding:3px 8px;border-radius:6px;background:rgba(0,0,0,0.45);color:#fff}} .pct-up{{color:#4ade80}} .pct-down{{color:#f87171}}
.dots{{display:inline-flex;align-items:center;background:rgba(0,0,0,0.18);padding:2px 7px;border-radius:12px;gap:3px}} .dot{{width:9px;height:9px;border-radius:50%;display:inline-block;border:1px solid rgba(0,0,0,0.2)}} .dot.橙{{background:#ff8a00}} .dot.綠{{background:#00c853}} .dot.藍{{background:#2962ff}} .dot.紅{{background:#d50000}} .dot.灰{{background:#94a3b8}} .dot.白{{background:#fff;border:1px solid #000}} .arrow{{font-size:9px}}
.rsi-inline{{font-size:10px;font-weight:900;padding:2px 7px;border-radius:6px;border:1px solid transparent;background:rgba(168,85,247,0.18);color:#e9d5ff}} .rsi-inline.rsi-green{{border-color:#22c55e;background:rgba(34,197,94,0.15);color:#bbf7d0}} .rsi-inline.rsi-red{{border-color:#ef4444;background:rgba(239,68,68,0.15);color:#fecaca}}
.ma-box{{margin-top:6px;background:#000;border-radius:8px;padding:7px 9px;border:1px solid #111}} /* 不透明黑底 */
.ma-row{{font-size:11px;line-height:1.7;display:flex;flex-wrap:wrap;gap:6px;align-items:center}} 
.ma-w{{color:#ffffff;font-weight:600}} /* 日K 時K MA20等白色 */
.ma-item{{white-space:nowrap}} .ma-green{{color:#4ade80;font-weight:900}} .ma-red{{color:#f87171;font-weight:900}} .ma-same{{color:#ffffff}}
.pill{{padding:5px 10px;border-radius:18px;background:#1e293b;font-size:11px;margin:3px;display:inline-block;border:1px solid #334155}}
.rule-box{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px;margin:14px 0;font-size:11px;line-height:1.8}}
.ver{{background:#78350f;color:#fde68a;border:1px solid #92400e;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:800}}
</style><meta http-equiv="refresh" content="300"></head><body>
<div id="lock"><h2 style="margin:0 0 8px">🔒 私有看板</h2><div style="color:#94a3b8;font-size:13px">請輸入密碼</div><input id="pw" type="password" placeholder="請輸入密碼"/><button onclick="check()">進入</button></div>

<div class="header">
<h1>🚀 MA(20/60/240) 私有版 <span class="ver">V10</span></h1>
<div class="search"><span class="icon">🔍</span><input id="search" type="text" placeholder="搜索代號或名稱，例如 TSLA 特斯拉 / NVDA 輝達 (模糊搜索)" /></div>
</div>

<div class="sub">更新: {hk_now} 香港時間 | 共{len(results)}隻 | 當前價含盤前後 時k含盤前後 | 排序橙>綠>藍>紅>灰>白</div>
<div style="margin-bottom:8px">
<span class="pill">🟠橙 主升 {len([r for r in results if r['today']=='橙'])}隻</span>
<span class="pill">🟢綠 次強 {len([r for r in results if r['today']=='綠'])}隻</span>
<span class="pill">🔵藍 弱 {len([r for r in results if r['today']=='藍'])}隻</span>
<span class="pill">🔴紅 空頭 {len([r for r in results if r['today']=='紅'])}隻</span>
<span class="pill">⚪灰 震盪 {len([r for r in results if r['today']=='灰'])}隻</span>
<span class="pill" style="background:#fff;color:#000">⬜白 限流 {len([r for r in results if r['today']=='白'])}隻</span>
</div>
<div class="grid" id="grid">{cards}</div>
<div class="rule-box">
<b>技術指標MA(20，60，240)：</b><br>
🟠 股價日k站上MA60，時k站上MA60和MA240。<br>
🟢 股價日k站上MA60，時k站上MA60（時k未站上240MA）。<br>
🔵 股價日k跌穿MA20，時k跌穿MA20。<br>
🔴 股價日k跌穿MA60，時k跌穿MA20和MA60。<br>
⚪ 不符合以上條件。<br>
⬜ 白=限流
</div>
<script>
const REAL_PW="{WEB_PASSWORD}";
function check(){{const v=document.getElementById('pw').value;if(v===REAL_PW){{document.getElementById('lock').style.display='none';sessionStorage.setItem('ma_pw','ok');}}else{{alert('密碼錯誤');}}}}
if(sessionStorage.getItem('ma_pw')==='ok')document.getElementById('lock').style.display='none';
document.getElementById('pw').addEventListener('keydown',e=>{{if(e.key==='Enter')check();}});

// 模糊搜索 代號或名稱
const searchInput = document.getElementById('search');
const grid = document.getElementById('grid');
searchInput.addEventListener('input', (e)=>{{
  const q = e.target.value.trim().toLowerCase();
  const cards = grid.querySelectorAll('.card');
  cards.forEach(card=>{{
    const code = card.getAttribute('data-code')||'';
    const name = card.getAttribute('data-name')||'';
    if(!q) card.classList.remove('hide');
    else {{
      if(code.includes(q) || name.includes(q)) card.classList.remove('hide');
      else card.classList.add('hide');
    }}
  }});
}});
</script>
</body></html>
"""
with open("docs/index.html","w",encoding="utf-8") as f:
    f.write(html)
print("V10 已生成 搜索框 RSI括號 黑底不透明 白字 去密碼")
