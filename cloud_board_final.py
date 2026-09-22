import yfinance as yf
import pandas as pd
from datetime import datetime
import json
import os
import requests

# ========== 配置區 ==========
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")  # 在GitHub Secrets裡設置
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
WEB_PASSWORD = "8888"  # 你的看板密碼，自己改
# ===========================

WATCHLIST = [
    ("DXYZ", "Destiny Tech100"), ("SMCI", "超微電腦"), ("PENG", "Penguin Solutions"),
    ("NBIS", "Nebius Group"), ("BE", "Bloom Energy"), ("BEZ", "2X Short BE"),
    ("MU", "美光科技"), ("MUU", "美光2X"), ("MUZ", "美光Bear"), ("SNDK", "SanDisk"),
    ("SOXX", "半導體ETF"), ("SOXL", "半導體3X"), ("CRCL", "Circle"), ("CRCG", "Circle2X"),
    ("CRCD", "Circle反向2X"), ("UPRO", "標普3X"), ("TQQQ", "納指3X"), ("SQQQ", "納指3X空"),
    ("9868.HK", "小鵬-W"), ("XPEV", "小鵬ADR"), ("TSLA", "特斯拉"), ("SPY", "標普500"),
    ("QQQ", "納指QQQ"), ("LI", "理想"), ("NIO", "蔚來"), ("BABA", "阿里"), ("FUTU", "富途"),
    ("NVDA", "輝達"), ("AMD", "超微半導體"), ("INTC", "英特爾"), ("AAPL", "蘋果"),
    ("GOOGL", "谷歌-A"), ("GOOG", "谷歌-C"), ("MSFT", "微軟"), ("AMZN", "亞馬遜"),
]

def calc_color(df_day, df_60m, idx_day=-1):
    try:
        if len(df_day) < 70: return "灰"
        if isinstance(df_day.columns, pd.MultiIndex): df_day = df_day.droplevel(0, axis=1) if len(df_day.columns.levels[0])==1 else df_day
        if isinstance(df_60m.columns, pd.MultiIndex): df_60m = df_60m.droplevel(0, axis=1) if len(df_60m.columns.levels[0])==1 else df_60m
        d_close = float(df_day['Close'].iloc[idx_day])
        d_ma20 = float(df_day['Close'].rolling(20).mean().iloc[idx_day])
        d_ma60 = float(df_day['Close'].rolling(60).mean().iloc[idx_day])
        h_close = float(df_60m['Close'].iloc[-1]) if not df_60m.empty else d_close
        h_ma20 = float(df_60m['Close'].rolling(20).mean().iloc[-1]) if not df_60m.empty and len(df_60m)>=20 else d_ma20
        h_ma60 = float(df_60m['Close'].rolling(60).mean().iloc[-1]) if not df_60m.empty and len(df_60m)>=60 else d_ma60
        h_ma240 = float(df_60m['Close'].rolling(240).mean().iloc[-1]) if not df_60m.empty and len(df_60m)>=240 else h_ma60
        if pd.isna(d_ma60) or pd.isna(h_ma60): return "灰"
        if d_close < d_ma60 and h_close < h_ma20 and h_close < h_ma60: return "紅"
        if d_close < d_ma20 and h_close < h_ma20: return "藍"
        if d_close > d_ma60 and h_close > h_ma240 and h_close > h_ma60: return "橙"
        if d_close > d_ma60 and h_close > h_ma60: return "綠"
        return "灰"
    except: return "灰"

results = []
for code, name in WATCHLIST:
    try:
        df_day = yf.download(code, period="1y", interval="1d", progress=False, auto_adjust=True)
        df_60m = yf.download(code, period="3mo", interval="60m", progress=False, auto_adjust=True)
        if df_day.empty: continue
        today = calc_color(df_day, df_60m, -1)
        yesterday = calc_color(df_day, df_60m, -2) if len(df_day)>=2 else "灰"
        close_price = float(df_day['Close'].iloc[-1])
        prev_close = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else close_price
        pct = (close_price/prev_close-1)*100 if prev_close else 0
        change = "→" if today==yesterday else f"{yesterday}→{today}"
        results.append({"code": code, "name": name, "today": today, "yesterday": yesterday, "close": round(close_price,2), "pct": round(pct,2), "change": change})
        print(f"{code} 昨:{yesterday} 今:{today}")
    except Exception as e:
        print(f"{code} err {e}")

order = {"紅":0,"藍":1,"灰":2,"綠":3,"橙":4}
results.sort(key=lambda x: order.get(x["today"],2))

os.makedirs("docs", exist_ok=True)
# 保存今日用於下次對比
with open("docs/data.json", "w", encoding="utf-8") as f:
    json.dump({"update": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"), "results": results}, f, ensure_ascii=False, indent=2)

# 檢測變化，發Telegram
changes = [r for r in results if "→" in r["change"] and r["change"]!="→" and r["change"]!="灰→灰"]
if changes and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    msg = f"🔔 MA看板變化 {datetime.now().strftime('%m-%d %H:%M')} (5分刷新)\n"
    for r in changes[:10]:
        msg += f"{r['code']} {r['name']} {r['change']} 收盤{r['close']} {r['pct']}%\n"
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        print("Telegram已發送")
    except Exception as e:
        print(f"Telegram失敗 {e}")

# 生成帶密碼鎖的HTML
html = f"""
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MA看板 私有版</title>
<style>
body{{font-family:-apple-system,Helvetica,Arial;background:#0a0e14;color:#e6e6e6;padding:12px;margin:0}}
#lock{{position:fixed;inset:0;background:#0a0e14;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:9999}}
#lock input{{padding:12px 16px;border-radius:10px;border:1px solid #333;background:#1f2937;color:#fff;font-size:18px;text-align:center;margin:12px}}
#lock button{{padding:10px 24px;border-radius:10px;border:none;background:#ff8a00;color:#000;font-weight:700;font-size:16px;cursor:pointer}}
h1{{font-size:22px;margin:10px 0}} .sub{{color:#8a9199;font-size:12px;margin-bottom:14px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}}
.card{{border-radius:14px;padding:12px 14px;display:flex;justify-content:space-between;align-items:center}}
.橙{{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000}}
.綠{{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000}}
.灰{{background:#1f2937;color:#cbd5e1}}
.藍{{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff}}
.紅{{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff}}
.badge{{padding:5px 12px;border-radius:20px;font-weight:800;font-size:15px;background:rgba(0,0,0,0.15)}}
.small{{font-size:11px;opacity:0.85;margin-top:2px}}
.change{{font-size:11px;padding:2px 6px;border-radius:6px;background:rgba(255,255,255,0.25);margin-left:6px}}
.up{{color:#00e676}} .down{{color:#ff5252}}
.pill{{padding:6px 10px;border-radius:20px;background:#1f2937;font-size:12px;margin:4px;display:inline-block}}
</style><meta http-equiv="refresh" content="300"></head><body>
<div id="lock">
<h2 style="margin:0 0 10px">🔒 私有看板</h2>
<div style="color:#8a9199;font-size:13px">請輸入密碼才能查看</div>
<input id="pw" type="password" placeholder="輸入密碼 8888" />
<button onclick="check()">進入看板</button>
<div style="color:#666;font-size:11px;margin-top:12px">密碼錯誤會一直鎖住，別人就算知道網址也看不到</div>
</div>

<h1>🚀 MA(20/60/240) 私有版 <span style="font-size:11px;background:#ff8a00;color:#000;padding:3px 8px;border-radius:8px">每5分最快更新</span></h1>
<div class="sub">更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} | 昨天 vs 今天 | 共{len(results)}隻 | 密碼保護 + Telegram推送</div>
<div style="margin-bottom:12px">
<span class="pill">🟠橙 主升 {len([r for r in results if r['today']=='橙'])}隻</span>
<span class="pill">🟢綠 次強 {len([r for r in results if r['today']=='綠'])}隻</span>
<span class="pill">⚪灰 震盪 {len([r for r in results if r['today']=='灰'])}隻</span>
<span class="pill">🔵藍 弱 {len([r for r in results if r['today']=='藍'])}隻</span>
<span class="pill">🔴紅 空頭 {len([r for r in results if r['today']=='紅'])}隻</span>
</div>
<div class="grid">
"""

for r in results:
    pct_class = "up" if r['pct']>=0 else "down"
    pct_sign = "+" if r['pct']>=0 else ""
    arrow = f"<span class='change'>{r['change']}</span>" if r['change']!="→" else ""
    html += f"""
<div class="card {r['today']}">
<div><b>{r['code']}</b> {r['name']} {arrow}<div class="small">昨:{r['yesterday']} 今:{r['today']} | 收盤 {r['close']} <span class="{pct_class}">{pct_sign}{r['pct']}%</span></div></div>
<div class="badge">{r['today']}</div>
</div>
"""

html += f"""
</div>
<script>
const REAL_PW = "{WEB_PASSWORD}";
function check(){{ const v=document.getElementById('pw').value; if(v===REAL_PW){{ document.getElementById('lock').style.display='none'; localStorage.setItem('ma_pw','{WEB_PASSWORD}'); }} else {{ alert('密碼錯誤'); }} }}
if(localStorage.getItem('ma_pw')==="{WEB_PASSWORD}") document.getElementById('lock').style.display='none';
document.getElementById('pw').addEventListener('keydown',e=>{{ if(e.key==='Enter') check(); }});
</script>
</body></html>
"""

with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("已生成 docs/index.html 帶密碼鎖")
