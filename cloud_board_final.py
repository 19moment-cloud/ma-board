import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import json, os, time

WEB_PASSWORD = "88666666"
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
    except Exception as e:
        print(f"{ticker} 失敗 {e}")
        return pd.DataFrame()

def calc_color_and_detail(df_day, df_60m):
    try:
        if len(df_day) < 61: return "灰", "數據不足", 0,0
        d_close = float(df_day['Close'].iloc[-1])
        d_ma20 = float(df_day['Close'].rolling(20).mean().iloc[-1])
        d_ma60 = float(df_day['Close'].rolling(60).mean().iloc[-1])
        if df_60m.empty or len(df_60m) < 60:
            h_close, h_ma20, h_ma60, h_ma240 = d_close, d_ma20, d_ma60, d_ma60
        else:
            h_close = float(df_60m['Close'].iloc[-1])
            h_ma20 = float(df_60m['Close'].rolling(20).mean().iloc[-1])
            h_ma60 = float(df_60m['Close'].rolling(60).mean().iloc[-1])
            h_ma240 = float(df_60m['Close'].rolling(240).mean().iloc[-1]) if len(df_60m)>=240 else float(df_60m['Close'].mean())
        if pd.isna(d_ma60): return "灰", "均線空", d_close, d_ma60
        if d_close < d_ma60 and h_close < h_ma20 and h_close < h_ma60: return "紅", f"日{d_close:.0f}<MA60", d_close, d_ma60
        if d_close < d_ma20 and h_close < h_ma20: return "藍", f"日{d_close:.0f}<MA20", d_close, d_ma60
        if d_close > d_ma60 and h_close > h_ma240 and h_close > h_ma60: return "橙", f"日{d_close:.0f}>MA60 時>MA240", d_close, d_ma60
        if d_close > d_ma60 and h_close > h_ma60: return "綠", f"日{d_close:.0f}>MA60", d_close, d_ma60
        return "灰", f"纏繞{d_ma60:.0f}", d_close, d_ma60
    except Exception as e:
        return "灰", f"錯誤", 0,0

results = []
for code, name in WATCHLIST:
    try:
        print(f"===> {code}")
        df_day = get_history(code, "1y", "1d", False)
        if df_day.empty:
            results.append({"code": code, "name": name, "today": "灰", "yesterday": "灰", "curr": 0, "pct": 0, "change_dot": "", "detail": "失敗", "rsi_html": ""})
            time.sleep(1.2); continue
        df_60m = get_history(code, "60d", "60m", True)
        curr_price = float(df_60m['Close'].iloc[-1]) if not df_60m.empty else float(df_day['Close'].iloc[-1])
        prev_close = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else float(df_day['Close'].iloc[-1])
        pct = (curr_price/prev_close-1)*100 if prev_close else 0
        today, detail, d_close, d_ma60 = calc_color_and_detail(df_day, df_60m)
        yesterday, _, _, _ = calc_color_and_detail(df_day.iloc[:-1], df_60m) if len(df_day)>=2 else ("灰","",0,0)
        # 變化用圓點
        if today==yesterday:
            change_dot = f"<span class='dot {yesterday}'></span>→<span class='dot {today}'></span>"
        else:
            change_dot = f"<span class='dot {yesterday}'></span>→<span class='dot {today}'></span>"
        rsi6 = rsi(df_day['Close'], 6).iloc[-1]
        rsi14 = rsi(df_day['Close'], 14).iloc[-1]
        rsi24 = rsi(df_day['Close'], 24).iloc[-1]
        rsi_parts = []
        for label, val in [("6", rsi6), ("14", rsi14), ("24", rsi24)]:
            if pd.isna(val): continue
            if val >= 70 or val <= 30:
                rsi_parts.append(f"<span class='rsi-purple'>RSI{label} {val:.0f}</span>")
        rsi_html = " ".join(rsi_parts)
        results.append({"code": code, "name": name, "today": today, "yesterday": yesterday, "curr": round(curr_price,2), "pct": round(pct,2), "change_dot": change_dot, "detail": detail, "rsi_html": rsi_html})
        time.sleep(1.0)
    except Exception as e:
        print(f"{code} 錯 {e}")
        results.append({"code": code, "name": name, "today": "灰", "yesterday": "灰", "curr": 0, "pct": 0, "change_dot": "", "detail": "錯", "rsi_html": ""})

order = {"灰":0, "紅":1, "藍":2, "綠":3, "橙":4}
results.sort(key=lambda x: order.get(x["today"],0), reverse=True)

os.makedirs("docs", exist_ok=True)
with open("docs/data.json", "w", encoding="utf-8") as f:
    json.dump({"update": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"), "results": results}, f, ensure_ascii=False, indent=2)

cards_html = ""
for r in results:
    pct_class = "up" if r['pct']>=0 else "down"
    sign = "+" if r['pct']>=0 else ""
    rule_text = "🟠主升" if r['today']=="橙" else "🟢次強" if r['today']=="綠" else "⚪震盪" if r['today']=="灰" else "🔵弱" if r['today']=="藍" else "🔴空頭"
    curr_html = f"<span class='price'>${r['curr']}</span>" if r['curr']>0 else "<span class='price-err'>--</span>"
    pct_html = f"<span class='{pct_class}'>{sign}{r['pct']:.2f}%</span>" if r['curr']>0 else ""
    rsi_block = f"<div class='rsi'>{r['rsi_html']}</div>" if r['rsi_html'] else ""
    cards_html += f"""
<div class="card {r['today']}">
<div style="flex:1;min-width:0">
<div style="display:flex;align-items:center;flex-wrap:wrap;gap:6px"><b>{r['code']}</b> {r['name']} <span class="yday-dots">昨{r['yesterday'][:1]}<span class="dot {r['yesterday']}"></span> 今{r['today'][:1]}<span class="dot {r['today']}"></span> {r['change_dot']}</span></div>
<div class="line1">{curr_html} {pct_html}</div>
<div class="small">{rule_text} | {r['detail']}</div>
{rsi_block}
</div>
<div class="badge">{r['today']}</div>
</div>"""

# 為昨今圓點的簡潔版：直接用圓點取代字
# 更直觀版本：昨:● 今:●
cards_html_v2 = ""
for r in results:
    pct_class = "up" if r['pct']>=0 else "down"
    sign = "+" if r['pct']>=0 else ""
    curr_html = f"<span class='price'>${r['curr']}</span>" if r['curr']>0 else "--"
    pct_html = f"<span class='{pct_class}'>{sign}{r['pct']:.2f}%</span>" if r['curr']>0 else ""
    rule_text = "主升" if r['today']=="橙" else "次強" if r['today']=="綠" else "震盪" if r['today']=="灰" else "弱" if r['today']=="藍" else "空頭"
    rsi_block = f"<div class='rsi'>{r['rsi_html']}</div>" if r['rsi_html'] else ""
    cards_html_v2 += f"""
<div class="card {r['today']}">
<div style="flex:1;min-width:0">
<b>{r['code']}</b> {r['name']} <span class="change-dots"><span class="dot {r['yesterday']}" title="昨{r['yesterday']}"></span><span style="margin:0 2px">→</span><span class="dot {r['today']}" title="今{r['today']}"></span></span>
<div class="line1">{curr_html} {pct_html} <span class="yday" style="font-size:11px">昨<span class="dot {r['yesterday']}"></span> 今<span class="dot {r['today']}"></span></span></div>
<div class="small">{rule_text} | {r['detail']}</div>
{rsi_block}
</div>
<div class="badge">{r['today']}</div>
</div>"""

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MA看板 私有版</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,Helvetica,Arial;background:#0a0e14;color:#e6e6e6;padding:14px;margin:0;overflow-x:hidden}}
#lock{{position:fixed;inset:0;background:#0a0e14;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:9999}}
#lock input{{padding:14px 18px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:18px;text-align:center;margin:14px;width:240px}}
#lock button{{padding:12px 28px;border-radius:12px;border:none;background:#f59e0b;color:#000;font-weight:800;font-size:16px;cursor:pointer}}
h1{{font-size:20px;margin:12px 0}} .sub{{color:#94a3b8;font-size:12px;margin-bottom:12px;line-height:1.6}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;align-items:start}}
.card{{border-radius:14px;padding:12px 14px;display:flex;justify-content:space-between;align-items:flex-start;box-shadow:0 2px 8px rgba(0,0,0,0.4);gap:10px;min-height:88px}}
.橙{{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000}} .綠{{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000}}
.灰{{background:#1e293b;color:#cbd5e1;border:1px solid #2a3441}} .藍{{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff}} .紅{{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff}}
.badge{{padding:6px 14px;border-radius:20px;font-weight:800;font-size:16px;background:rgba(0,0,0,0.18);min-width:32px;text-align:center;flex-shrink:0}}
.line1{{font-size:13px;margin-top:5px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}} 
.price{{color:#facc15;font-weight:900;font-size:15px;background:rgba(0,0,0,0.28);padding:2px 8px;border-radius:6px}} 
.yday{{opacity:0.9;font-size:11px}} .small{{font-size:11px;opacity:0.92;margin-top:4px;line-height:1.4}} 
.up{{color:#00e676;font-weight:700}} .down{{color:#ff8a80;font-weight:700}} 
.rsi{{margin-top:4px;display:flex;gap:6px;flex-wrap:wrap}} .rsi-purple{{color:#e9d5ff;background:rgba(168,85,247,0.25);border:1px solid rgba(168,85,247,0.6);padding:2px 7px;border-radius:6px;font-size:11px;font-weight:900}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-left:3px;vertical-align:middle;border:1px solid rgba(0,0,0,0.2)}} 
.dot.橙{{background:#ff8a00}} .dot.綠{{background:#00c853}} .dot.灰{{background:#94a3b8}} .dot.藍{{background:#2962ff}} .dot.紅{{background:#d50000}}
.change-dots{{display:inline-flex;align-items:center;background:rgba(0,0,0,0.15);padding:2px 6px;border-radius:12px;margin-left:6px}}
.pill{{padding:6px 12px;border-radius:20px;background:#1e293b;font-size:12px;margin:3px;display:inline-block;border:1px solid #334155}}
.rule-box{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:12px;margin:14px 0;font-size:12px;line-height:1.8}}
</style><meta http-equiv="refresh" content="300"></head><body>
<div id="lock">
<h2 style="margin:0 0 8px">🔒 私有看板</h2>
<div style="color:#94a3b8;font-size:13px">請輸入密碼才能查看</div>
<input id="pw" type="password" placeholder="請輸入密碼" />
<button onclick="check()">進入看板</button>
</div>
<h1>🚀 MA(20/60/240) 私有版 <span style="font-size:11px;background:#f59e0b;color:#000;padding:4px 10px;border-radius:8px">V5 圓點+RSI</span></h1>
<div class="sub">更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} | 共{len(results)}隻 | 密碼 88666666 | 當前價含盤前後 | 排序橙>綠>藍>紅>灰 | RSI(6,14,24) 70/30 紫字</div>
<div style="margin-bottom:10px">
<span class="pill">🟠橙 主升 {len([r for r in results if r['today']=='橙'])}隻</span>
<span class="pill">🟢綠 次強 {len([r for r in results if r['today']=='綠'])}隻</span>
<span class="pill">🔵藍 弱 {len([r for r in results if r['today']=='藍'])}隻</span>
<span class="pill">🔴紅 空頭 {len([r for r in results if r['today']=='紅'])}隻</span>
<span class="pill">⚪灰 震盪 {len([r for r in results if r['today']=='灰'])}隻</span>
</div>
<div class="grid">{cards_html_v2}</div>
<div class="rule-box">
<b>📏 V5 升級（按你圖確認）：</b><br>
<b>RSI：</b> 正是你圖中的 <b>RSI 相對強弱指數 長度6/14/24 Upper70 Lower30 來源收盤</b>，已按此計算日線RSI<br>
只有 <b>>70超買 或 <30超賣</b> 才會用 <span class="rsi-purple">RSI14 78</span> 紫字顯示，30-70正常不顯示<br>
<b>昨今：</b> 已改成小圓點 <span class="dot 橙"></span>→<span class="dot 綠"></span> 取代 昨:橙 今:橙 文字，一眼看變化<br>
<b>當前價：</b> 黃字 $ 是小時線最新價（含盤前盤後），每5分鐘動<br>
<b>排序：</b> 橙>綠>藍>紅>灰
</div>
<script>
const REAL_PW = "{WEB_PASSWORD}";
function check(){{ const v=document.getElementById('pw').value; if(v===REAL_PW){{ document.getElementById('lock').style.display='none'; sessionStorage.setItem('ma_pw','ok'); }} else {{ alert('密碼錯誤'); }} }}
if(sessionStorage.getItem('ma_pw')==='ok') document.getElementById('lock').style.display='none';
document.getElementById('pw').addEventListener('keydown',e=>{{ if(e.key==='Enter') check(); }});
</script>
</body></html>
"""
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"V5 圓點+RSI 已生成 {len(results)} 隻")
