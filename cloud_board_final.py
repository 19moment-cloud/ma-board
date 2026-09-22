import yfinance as yf
import pandas as pd
from datetime import datetime
import json, os, requests, time

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

def get_history(ticker, period, interval, prepost):
    try:
        # 用單隻 Ticker 抓，比 download 穩定，不會被限流
        tk = yf.Ticker(ticker)
        df = tk.history(period=period, interval=interval, prepost=prepost, auto_adjust=True)
        if df.empty:
            # 重試一次
            time.sleep(0.8)
            df = tk.history(period=period, interval=interval, prepost=prepost, auto_adjust=True)
        return df
    except Exception as e:
        print(f"{ticker} {interval} 失敗 {e}")
        return pd.DataFrame()

def calc_color(df_day, df_60m, idx_day=-1):
    try:
        if len(df_day) < 61: return "灰", "數據不足61天"
        d_close = float(df_day['Close'].iloc[idx_day])
        d_ma20 = float(df_day['Close'].rolling(20).mean().iloc[idx_day])
        d_ma60 = float(df_day['Close'].rolling(60).mean().iloc[idx_day])
        
        # 小時線包含盤前盤後
        if df_60m.empty or len(df_60m) < 60:
            # 沒小時線就用日線代替，但標記
            h_close, h_ma20, h_ma60, h_ma240 = d_close, d_ma20, d_ma60, d_ma60
            h_note = "無小時線用日線"
        else:
            h_close = float(df_60m['Close'].iloc[-1])
            h_ma20 = float(df_60m['Close'].rolling(20).mean().iloc[-1])
            h_ma60 = float(df_60m['Close'].rolling(60).mean().iloc[-1])
            h_ma240 = float(df_60m['Close'].rolling(240).mean().iloc[-1]) if len(df_60m)>=240 else float(df_60m['Close'].mean())
            h_note = f"時{len(df_60m)}根含盤前後"
        
        if pd.isna(d_ma60) or pd.isna(h_ma60): return "灰", "均線為空"
        if d_close < d_ma60 and h_close < h_ma20 and h_close < h_ma60: return "紅", f"日{d_close:.1f}<MA60({d_ma60:.1f}) 時{h_close:.1f}<MA20/60 | {h_note}"
        if d_close < d_ma20 and h_close < h_ma20: return "藍", f"日{d_close:.1f}<MA20({d_ma20:.1f}) 時弱 | {h_note}"
        if d_close > d_ma60 and h_close > h_ma240 and h_close > h_ma60: return "橙", f"日{d_close:.1f}>MA60({d_ma60:.1f}) 時>MA240({h_ma240:.1f}) | {h_note}"
        if d_close > d_ma60 and h_close > h_ma60: return "綠", f"日{d_close:.1f}>MA60({d_ma60:.1f}) 時>MA60 | {h_note}"
        return "灰", f"日{d_close:.1f} 纏繞MA60({d_ma60:.1f}) | {h_note}"
    except Exception as e:
        return "灰", f"計算錯誤:{e}"

results = []
for code, name in WATCHLIST:
    try:
        print(f"===> {code}")
        df_day = get_history(code, "1y", "1d", False)
        if df_day.empty:
            print(f"{code} 日線空 -> 跳過，標灰")
            results.append({"code": code, "name": name, "today": "灰", "yesterday": "灰", "close": 0, "pct": 0, "change": "錯誤→灰", "detail": "日線抓取失敗 Yahoo限流，重試中"})
            time.sleep(1.2)
            continue
        df_60m = get_history(code, "60d", "60m", True)  # 關鍵：prepost=True 包含盤前盤後
        
        today, detail_today = calc_color(df_day, df_60m, -1)
        yesterday, _ = calc_color(df_day, df_60m, -2) if len(df_day)>=2 else ("灰","")
        close_price = float(df_day['Close'].iloc[-1])
        prev_close = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else close_price
        pct = (close_price/prev_close-1)*100 if prev_close else 0
        change = "→" if today==yesterday else f"{yesterday}→{today}"
        results.append({"code": code, "name": name, "today": today, "yesterday": yesterday, "close": round(close_price,2), "pct": round(pct,2), "change": change, "detail": detail_today})
        time.sleep(1.0)  # 間隔1秒，避免被Yahoo封
    except Exception as e:
        print(f"{code} 總錯誤 {e}")
        results.append({"code": code, "name": name, "today": "灰", "yesterday": "灰", "close": 0, "pct": 0, "change": "錯誤", "detail": str(e)[:80]})

# 排序 橙>綠>灰>藍>紅
order = {"紅":0,"藍":1,"灰":2,"綠":3,"橙":4}
results.sort(key=lambda x: order.get(x["today"],2), reverse=True)

os.makedirs("docs", exist_ok=True)
with open("docs/data.json", "w", encoding="utf-8") as f:
    json.dump({"update": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"), "results": results}, f, ensure_ascii=False, indent=2)

cards_html = ""
for r in results:
    pct_class = "up" if r['pct']>=0 else "down"
    sign = "+" if r['pct']>=0 else ""
    arrow = f"<span class='change'>{r['change']}</span>" if r['change']!="→" else ""
    rule_text = "🟠主升" if r['today']=="橙" else "🟢次強" if r['today']=="綠" else "⚪震盪" if r['today']=="灰" else "🔵弱" if r['today']=="藍" else "🔴空頭"
    # 黃字股價
    price_html = f"<span class='price'>${r['close']}</span>" if r['close']>0 else "<span class='price-err'>抓取失敗</span>"
    pct_html = f"<span class='{pct_class}'>{sign}{r['pct']}%</span>" if r['close']>0 else ""
    cards_html += f"""
<div class="card {r['today']}">
<div style="flex:1">
<b>{r['code']}</b> {r['name']} {arrow}<br>
<div class="line1">{price_html} {pct_html} <span style="opacity:0.8">| 昨:{r['yesterday']} 今:{r['today']}</span></div>
<div class="small">{rule_text} | {r['detail']}</div>
</div>
<div class="badge">{r['today']}</div>
</div>"""

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MA看板 私有版</title>
<style>
body{{font-family:-apple-system,Helvetica,Arial;background:#0a0e14;color:#e6e6e6;padding:14px;margin:0}}
#lock{{position:fixed;inset:0;background:#0a0e14;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:9999}}
#lock input{{padding:14px 18px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:18px;text-align:center;margin:14px;width:240px}}
#lock button{{padding:12px 28px;border-radius:12px;border:none;background:#f59e0b;color:#000;font-weight:800;font-size:16px;cursor:pointer}}
h1{{font-size:20px;margin:12px 0}} .sub{{color:#94a3b8;font-size:12px;margin-bottom:12px;line-height:1.6}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:10px}}
.card{{border-radius:14px;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,0.4);gap:10px}}
.橙{{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000}} .綠{{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000}}
.灰{{background:#1e293b;color:#cbd5e1}} .藍{{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff}} .紅{{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff}}
.badge{{padding:6px 14px;border-radius:20px;font-weight:800;font-size:16px;background:rgba(0,0,0,0.18);min-width:28px;text-align:center}}
.line1{{font-size:14px;margin-top:4px}} .price{{color:#facc15;font-weight:900;font-size:16px;background:rgba(0,0,0,0.25);padding:2px 8px;border-radius:6px}} .price-err{{color:#ff8a80;font-size:13px}}
.small{{font-size:11px;opacity:0.9;margin-top:5px;line-height:1.4}} .change{{font-size:11px;padding:3px 8px;border-radius:8px;background:rgba(255,255,255,0.25);margin-left:6px;font-weight:700}}
.up{{color:#00e676}} .down{{color:#ff5252}} .pill{{padding:6px 12px;border-radius:20px;background:#1e293b;font-size:12px;margin:3px;display:inline-block;border:1px solid #334155}}
.rule-box{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:12px;margin:14px 0;font-size:12px;line-height:1.8}}
</style><meta http-equiv="refresh" content="300"></head><body>
<div id="lock">
<h2 style="margin:0 0 8px">🔒 私有看板</h2>
<div style="color:#94a3b8;font-size:13px">請輸入密碼才能查看</div>
<input id="pw" type="password" placeholder="請輸入密碼" />
<button onclick="check()">進入看板</button>
</div>
<h1>🚀 MA(20/60/240) 私有版 <span style="font-size:11px;background:#f59e0b;color:#000;padding:4px 10px;border-radius:8px">每5分鐘含盤前後</span></h1>
<div class="sub">更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} | 共{len(results)}隻 | 密碼: 88666666 | 含盤前後小時線 | 自動刷新300秒 | 股價黃字可驗證</div>
<div style="margin-bottom:10px">
<span class="pill">🟠橙 主升 {len([r for r in results if r['today']=='橙'])}隻</span>
<span class="pill">🟢綠 次強 {len([r for r in results if r['today']=='綠'])}隻</span>
<span class="pill">⚪灰 震盪 {len([r for r in results if r['today']=='灰'])}隻</span>
<span class="pill">🔵藍 弱 {len([r for r in results if r['today']=='藍'])}隻</span>
<span class="pill">🔴紅 空頭 {len([r for r in results if r['today']=='紅'])}隻</span>
</div>
<div class="grid">{cards_html}</div>
<div class="rule-box">
<b>📏 你的規則（已恢復+升級含盤前後）：</b><br>
🟠 <b>橙 主升：</b> 日線收盤 > MA60 且 時線(60m含盤前後) > MA240 且 > MA60 (最強多頭)<br>
🟢 <b>綠 次強：</b> 日線收盤 > MA60 且 時線在MA60-240之間 (回踩)<br>
⚪ <b>灰 震盪：</b> 其他都在均線附近纏繞<br>
🔵 <b>藍 轉弱：</b> 日<MA20 且 時<MA20<br>
🔴 <b>紅 空頭：</b> 日<MA60 且 時<MA20 且 <MA60<br>
<br>
<b>黃字</b> 是當前股價，可對照富途驗證準確性。小時線已開啟 <code>prepost=True</code> 包含盤前盤後，真實有效。<br>
<b>變化提醒：</b> 顯示 昨天→今天，例如 灰→綠 就是剛轉強
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
print(f"V3 已生成 {len(results)} 隻，含盤前後，黃字股價")
