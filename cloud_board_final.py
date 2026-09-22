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
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))

def get_history(ticker, period, interval, prepost):
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=period, interval=interval, prepost=prepost, auto_adjust=True)
        if df.empty:
            time.sleep(0.8)
            df = tk.history(period=period, interval=interval, prepost=prepost, auto_adjust=True)
        return df
    except:
        return pd.DataFrame()

results = []
for code, name in WATCHLIST:
    try:
        df_day = get_history(code, "1y", "1d", False)
        if df_day.empty:
            results.append({"code":code,"name":name,"today":"灰","yesterday":"灰","curr":0,"pct":0,"d_ma60":0,"h_ma60":0,"h_ma240":0,"rsi14":None})
            time.sleep(1.2); continue
        df_60m = get_history(code, "60d", "60m", True)
        curr = float(df_60m['Close'].iloc[-1]) if not df_60m.empty else float(df_day['Close'].iloc[-1])
        prev = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else float(df_day['Close'].iloc[-1])
        pct = (curr/prev-1)*100 if prev else 0

        d_ma20 = float(df_day['Close'].rolling(20).mean().iloc[-1]) if len(df_day)>=20 else 0
        d_ma60 = float(df_day['Close'].rolling(60).mean().iloc[-1]) if len(df_day)>=60 else 0
        if not df_60m.empty and len(df_60m)>=60:
            h_ma20 = float(df_60m['Close'].rolling(20).mean().iloc[-1])
            h_ma60 = float(df_60m['Close'].rolling(60).mean().iloc[-1])
            h_ma240 = float(df_60m['Close'].rolling(240).mean().iloc[-1]) if len(df_60m)>=240 else float(df_60m['Close'].mean())
            h_close = float(df_60m['Close'].iloc[-1])
        else:
            h_ma20=h_ma60=h_ma240=h_close=curr

        d_close = float(df_day['Close'].iloc[-1])
        # 顏色邏輯
        if d_close < d_ma60 and h_close < h_ma20 and h_close < h_ma60: today="紅"
        elif d_close < d_ma20 and h_close < h_ma20: today="藍"
        elif d_close > d_ma60 and h_close > h_ma240 and h_close > h_ma60: today="橙"
        elif d_close > d_ma60 and h_close > h_ma60: today="綠"
        else: today="灰"

        # 昨天顏色
        if len(df_day)>=2:
            d2 = float(df_day['Close'].iloc[-2])
            d2_ma20 = float(df_day['Close'].rolling(20).mean().iloc[-2])
            d2_ma60 = float(df_day['Close'].rolling(60).mean().iloc[-2])
            yesterday = "灰"
            if d2 < d2_ma60 and h_close < h_ma20: yesterday="紅"
            elif d2 < d2_ma20: yesterday="藍"
            elif d2 > d2_ma60 and h_close > h_ma240: yesterday="橙"
            elif d2 > d2_ma60: yesterday="綠"
        else:
            yesterday="灰"

        rsi14 = float(rsi(df_day['Close'],14).iloc[-1]) if len(df_day)>=15 else None

        results.append({"code":code,"name":name,"today":today,"yesterday":yesterday,"curr":round(curr,2),"pct":round(pct,2),"d_ma60":round(d_ma60,2),"h_ma60":round(h_ma60,2),"h_ma240":round(h_ma240,2),"rsi14":rsi14})
        time.sleep(1.0)
    except Exception as e:
        results.append({"code":code,"name":name,"today":"灰","yesterday":"灰","curr":0,"pct":0,"d_ma60":0,"h_ma60":0,"h_ma240":0,"rsi14":None})

order = {"灰":0,"紅":1,"藍":2,"綠":3,"橙":4}
results.sort(key=lambda x: order.get(x["today"],0), reverse=True)

hk_now = datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M:%S 香港時間")
os.makedirs("docs", exist_ok=True)
with open("docs/data.json","w",encoding="utf-8") as f:
    json.dump({"update":hk_now,"results":results},f,ensure_ascii=False,indent=2)

cards=""
for r in results:
    pct_cls="up" if r['pct']>=0 else "down"
    sign="+" if r['pct']>=0 else ""
    curr_html=f"<span class='price'>${r['curr']}</span>" if r['curr']>0 else "--"
    pct_html=f"<span class='{pct_cls}'>{sign}{r['pct']:.2f}%</span>" if r['curr']>0 else ""
    # 只保留 圓點→圓點
    dots=f"<span class='dots'><span class='dot {r['yesterday']}'></span><span class='arrow'>→</span><span class='dot {r['today']}'></span></span>"
    # MA 價位直接標
    ma_html=f"<div class='ma'>MA60({r['d_ma60']:.0f}) 時MA60({r['h_ma60']:.0f}) MA240({r['h_ma240']:.0f})</div>"
    # RSI14 只要14，紫字，綠框>70 紅框<30
    rsi_html=""
    if r['rsi14'] is not None:
        if r['rsi14']>=70:
            rsi_html=f"<span class='rsi rsi-green'>RSI14 {r['rsi14']:.0f}</span>"
        elif r['rsi14']<=30:
            rsi_html=f"<span class='rsi rsi-red'>RSI14 {r['rsi14']:.0f}</span>"
        # 30-70 不顯示

    cards+=f"""
<div class="card {r['today']}">
  <div class="left">
    <div class="top"><b>{r['code']}</b> {r['name']} {dots}</div>
    <div class="mid">{curr_html} {pct_html}</div>
    {ma_html}
    {f"<div class='rsi-row'>{rsi_html}</div>" if rsi_html else ""}
  </div>
  <div class="badge">{r['today']}</div>
</div>"""

html=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MA看板 私有版</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial;background:#0a0e14;color:#e6e6e6;padding:14px;margin:0}}
#lock{{position:fixed;inset:0;background:#0a0e14;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:9999}}
#lock input{{padding:14px 18px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:18px;text-align:center;margin:14px;width:240px}}
#lock button{{padding:12px 28px;border-radius:12px;border:none;background:#f59e0b;color:#000;font-weight:800;font-size:16px;cursor:pointer}}
h1{{font-size:19px;margin:10px 0}} .sub{{color:#94a3b8;font-size:11px;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px;align-items:start}}
.card{{border-radius:14px;padding:12px 14px;display:flex;justify-content:space-between;align-items:flex-start;gap:10px;min-height:86px;overflow:hidden}}
.橙{{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000}} .綠{{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000}}
.灰{{background:#1e293b;color:#cbd5e1;border:1px solid #2a3441}} .藍{{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff}} .紅{{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff}}
.badge{{padding:5px 12px;border-radius:18px;font-weight:800;font-size:14px;background:rgba(0,0,0,0.18);min-width:28px;text-align:center;flex-shrink:0}}
.left{{flex:1;min-width:0}} .top{{font-size:13px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}} .mid{{margin-top:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.price{{color:#facc15;font-weight:900;font-size:15px;background:rgba(0,0,0,0.28);padding:2px 8px;border-radius:6px}}
.up{{color:#00e676;font-weight:800;font-size:12px}} .down{{color:#ff6b6b;font-weight:800;font-size:12px}}
.ma{{font-size:10px;opacity:0.9;margin-top:4px;word-break:break-all}} 
.dots{{display:inline-flex;align-items:center;background:rgba(0,0,0,0.18);padding:2px 8px;border-radius:12px;gap:4px;margin-left:4px}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;border:1px solid rgba(0,0,0,0.2)}} .dot.橙{{background:#ff8a00}} .dot.綠{{background:#00c853}} .dot.藍{{background:#2962ff}} .dot.紅{{background:#d50000}} .dot.灰{{background:#94a3b8}}
.arrow{{font-size:10px;opacity:0.8}}
.rsi-row{{margin-top:5px}} .rsi{{font-size:11px;font-weight:900;padding:2px 8px;border-radius:6px;background:rgba(168,85,247,0.18);color:#e9d5ff;border:1px solid transparent}}
.rsi-green{{border-color:#22c55e;color:#bbf7d0;background:rgba(34,197,94,0.15)}} .rsi-red{{border-color:#ef4444;color:#fecaca;background:rgba(239,68,68,0.15)}}
.pill{{padding:5px 10px;border-radius:18px;background:#1e293b;font-size:11px;margin:3px;display:inline-block;border:1px solid #334155}}
.rule-box{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:10px;margin:14px 0;font-size:11px;line-height:1.7}}
</style><meta http-equiv="refresh" content="300"></head><body>
<div id="lock"><h2 style="margin:0 0 8px">🔒 私有看板</h2><div style="color:#94a3b8;font-size:13px">請輸入密碼</div><input id="pw" type="password" placeholder="請輸入密碼"/><button onclick="check()">進入</button></div>
<h1>🚀 MA(20/60/240) 私有版 <span style="font-size:10px;background:#f59e0b;color:#000;padding:3px 8px;border-radius:8px">V6 香港時間+圓點+RSI14</span></h1>
<div class="sub">更新: {hk_now} | 共{len(results)}隻 | 密碼 88666666 | 當前價含盤前後 每5分 | 排序橙>綠>藍>紅>灰 | RSI14 70/30 紫字 綠框超買紅框超賣</div>
<div style="margin-bottom:8px">
<span class="pill">🟠橙 主升 {len([r for r in results if r['today']=='橙'])}隻</span>
<span class="pill">🟢綠 次強 {len([r for r in results if r['today']=='綠'])}隻</span>
<span class="pill">🔵藍 弱 {len([r for r in results if r['today']=='藍'])}隻</span>
<span class="pill">🔴紅 空頭 {len([r for r in results if r['today']=='紅'])}隻</span>
<span class="pill">⚪灰 震盪 {len([r for r in results if r['today']=='灰'])}隻</span>
</div>
<div class="grid">{cards}</div>
<div class="rule-box">
<b>V6 按你要求改：</b><br>
1. 時間改香港時間<br>
2. 昨今文字已移除，只留 <span class="dot 橙"></span>→<span class="dot 綠"></span> 圓點箭頭圓點<br>
3. MA直接顯示價位：MA60(價) 時MA60(價) MA240(價)<br>
4. RSI只留RSI14，>70綠框超買，<30紅框超賣，紫字透明底，30-70不顯示<br>
5. 排版已重寫，不會再疊
</div>
<script>
const REAL_PW="{WEB_PASSWORD}";
function check(){{const v=document.getElementById('pw').value;if(v===REAL_PW){{document.getElementById('lock').style.display='none';sessionStorage.setItem('ma_pw','ok');}}else{{alert('密碼錯誤');}}}}
if(sessionStorage.getItem('ma_pw')==='ok')document.getElementById('lock').style.display='none';
document.getElementById('pw').addEventListener('keydown',e=>{{if(e.key==='Enter')check();}});
</script>
</body></html>
"""
with open("docs/index.html","w",encoding="utf-8") as f:
    f.write(html)
print("V6 香港時間 圓點 MA價位 RSI14 綠紅框 已生成")
