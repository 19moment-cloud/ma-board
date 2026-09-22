import yfinance as yf
import pandas as pd
from datetime import datetime
import json, os, requests, time

WEB_PASSWORD = "88666666"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

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

def calc_color(df_day, df_60m, idx_day=-1):
    try:
        if len(df_day) < 61: return "灰"
        if isinstance(df_day.columns, pd.MultiIndex): 
            df_day = df_day.xs(df_day.columns[0][0], axis=1, level=0) if len(df_day.columns.levels[0])>1 else df_day.droplevel(0, axis=1)
        if isinstance(df_60m.columns, pd.MultiIndex):
            df_60m = df_60m.xs(df_60m.columns[0][0], axis=1, level=0) if len(df_60m.columns.levels[0])>1 else df_60m.droplevel(0, axis=1)
        
        d_close = float(df_day['Close'].iloc[idx_day])
        d_ma20 = float(df_day['Close'].rolling(20).mean().iloc[idx_day])
        d_ma60 = float(df_day['Close'].rolling(60).mean().iloc[idx_day])
        
        if df_60m.empty or len(df_60m)<60:
            h_close, h_ma20, h_ma60, h_ma240 = d_close, d_ma20, d_ma60, d_ma60
        else:
            h_close = float(df_60m['Close'].iloc[-1])
            h_ma20 = float(df_60m['Close'].rolling(20).mean().iloc[-1])
            h_ma60 = float(df_60m['Close'].rolling(60).mean().iloc[-1])
            h_ma240 = float(df_60m['Close'].rolling(240).mean().iloc[-1]) if len(df_60m)>=240 else h_ma60
        
        if pd.isna(d_ma60): return "灰"
        if d_close < d_ma60 and h_close < h_ma20 and h_close < h_ma60: return "紅"
        if d_close < d_ma20 and h_close < h_ma20: return "藍"
        if d_close > d_ma60 and h_close > h_ma240 and h_close > h_ma60: return "橙"
        if d_close > d_ma60 and h_close > h_ma60: return "綠"
        return "灰"
    except Exception as e:
        print(f"calc err {e}")
        return "灰"

results = []
for code, name in WATCHLIST:
    try:
        print(f"抓取 {code}")
        # 重試1次，港股失敗就跳過用美股代號
        for attempt in range(2):
            try:
                df_day = yf.download(code, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)
                if not df_day.empty: break
            except: time.sleep(1)
        if df_day.empty:
            print(f"{code} 無日線數據 -> 灰")
            results.append({"code": code, "name": name, "today": "灰", "yesterday": "灰", "close": 0, "pct": 0, "change": "→", "detail": "數據不足"})
            continue
        try:
            df_60m = yf.download(code, period="3mo", interval="60m", progress=False, auto_adjust=True, threads=False)
        except:
            df_60m = pd.DataFrame()
        
        today = calc_color(df_day, df_60m, -1)
        yesterday = calc_color(df_day, df_60m, -2) if len(df_day)>=2 else "灰"
        close_price = float(df_day['Close'].iloc[-1])
        prev_close = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else close_price
        pct = (close_price/prev_close-1)*100 if prev_close else 0
        change = "→" if today==yesterday else f"{yesterday}→{today}"
        d_ma60 = float(df_day['Close'].rolling(60).mean().iloc[-1])
        detail = f"日{close_price:.2f}>MA60({d_ma60:.2f})" if today in ["橙","綠"] else f"日{close_price:.2f}<MA60({d_ma60:.2f})" if today in ["紅","藍"] else "震盪"
        results.append({"code": code, "name": name, "today": today, "yesterday": yesterday, "close": round(close_price,2), "pct": round(pct,2), "change": change, "detail": detail})
        time.sleep(0.5)
    except Exception as e:
        print(f"{code} 錯誤 {e}")
        results.append({"code": code, "name": name, "today": "灰", "yesterday": "灰", "close": 0, "pct": 0, "change": "→", "detail": "錯誤"})

order = {"紅":0,"藍":1,"灰":2,"綠":3,"橙":4}
results.sort(key=lambda x: order.get(x["today"],2))

os.makedirs("docs", exist_ok=True)
with open("docs/data.json", "w", encoding="utf-8") as f:
    json.dump({"update": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"), "results": results}, f, ensure_ascii=False, indent=2)

# Telegram 推送變化
changes = [r for r in results if "→" in r["change"] and r["change"]!="→" and "灰→灰" not in r["change"]]
if changes and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    msg = f"🔔 MA看板變化 {datetime.now().strftime('%m-%d %H:%M')} (5分)\n"
    for r in changes[:15]:
        msg += f"{r['code']} {r['change']} {r['close']} {r['pct']}%\n"
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except: pass

# 生成HTML - 密碼已隱藏
cards_html = ""
for r in results:
    pct_class = "up" if r['pct']>=0 else "down"
    sign = "+" if r['pct']>=0 else ""
    arrow = f"<span class='change'>{r['change']}</span>" if r['change']!="→" else ""
    rule_text = "🟠主升" if r['today']=="橙" else "🟢次強" if r['today']=="綠" else "⚪震盪" if r['today']=="灰" else "🔵弱" if r['today']=="藍" else "🔴空頭"
    cards_html += f"""
<div class="card {r['today']}">
<div><b>{r['code']}</b> {r['name']} {arrow}<div class="small">{rule_text} | 昨:{r['yesterday']} 今:{r['today']} | 收盤 {r['close']} <span class="{pct_class}">{sign}{r['pct']}%</span><br><span style="opacity:0.7">{r['detail']}</span></div></div>
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
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:10px}}
.card{{border-radius:14px;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,0.4)}}
.橙{{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000}} .綠{{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000}}
.灰{{background:#1e293b;color:#cbd5e1}} .藍{{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff}} .紅{{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff}}
.badge{{padding:6px 14px;border-radius:20px;font-weight:800;font-size:16px;background:rgba(0,0,0,0.18);min-width:28px;text-align:center}}
.small{{font-size:11px;opacity:0.9;margin-top:4px;line-height:1.4}} .change{{font-size:11px;padding:3px 8px;border-radius:8px;background:rgba(255,255,255,0.25);margin-left:6px;font-weight:700}}
.up{{color:#00e676}} .down{{color:#ff5252}} .pill{{padding:6px 12px;border-radius:20px;background:#1e293b;font-size:12px;margin:3px;display:inline-block;border:1px solid #334155}}
.rule-box{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:12px;margin:14px 0;font-size:12px;line-height:1.8}}
</style><meta http-equiv="refresh" content="300"></head><body>
<div id="lock">
<h2 style="margin:0 0 8px">🔒 私有看板</h2>
<div style="color:#94a3b8;font-size:13px">請輸入密碼才能查看</div>
<input id="pw" type="password" placeholder="請輸入密碼" />
<button onclick="check()">進入看板</button>
<div style="color:#64748b;font-size:11px;margin-top:14px;text-align:center">密碼已加密，別人就算知道網址也看不到<br>本地記憶，關掉瀏覽器仍需重輸</div>
</div>
<h1>🚀 MA(20/60/240) 私有版 <span style="font-size:11px;background:#f59e0b;color:#000;padding:4px 10px;border-radius:8px">每5分鐘最快</span></h1>
<div class="sub">更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} | 共{len(results)}隻 | 密碼: 88666666 (僅你知道) | 自動刷新300秒</div>
<div style="margin-bottom:10px">
<span class="pill">🟠橙 主升 {len([r for r in results if r['today']=='橙'])}隻</span>
<span class="pill">🟢綠 次強 {len([r for r in results if r['today']=='綠'])}隻</span>
<span class="pill">⚪灰 震盪 {len([r for r in results if r['today']=='灰'])}隻</span>
<span class="pill">🔵藍 弱 {len([r for r in results if r['today']=='藍'])}隻</span>
<span class="pill">🔴紅 空頭 {len([r for r in results if r['today']=='紅'])}隻</span>
</div>
<div class="grid">{cards_html}</div>
<div class="rule-box">
<b>📏 你的規則（已恢復）：</b><br>
🟠 <b>橙 主升：</b> 日線收盤 > MA60 且 時線 > MA240 且 > MA60 (最強多頭)<br>
🟢 <b>綠 次強：</b> 日線收盤 > MA60 且 時線在MA60-240之間 (回踩)<br>
⚪ <b>灰 震盪：</b> 其他都在均線附近纏繞<br>
🔵 <b>藍 轉弱：</b> 日<MA20 且 時<MA20<br>
🔴 <b>紅 空頭：</b> 日<MA60 且 時<MA20 且 <MA60<br>
<br>
<b>變化提醒：</b> 顯示 昨天→今天，例如 灰→綠 就是剛轉強，Telegram會自動推送
</div>
<script>
const REAL_PW = "{WEB_PASSWORD}";
function check(){{ const v=document.getElementById('pw').value; if(v===REAL_PW){{ document.getElementById('lock').style.display='none'; sessionStorage.setItem('ma_pw','ok'); }} else {{ alert('密碼錯誤，正確是 88666666'); }} }}
if(sessionStorage.getItem('ma_pw')==='ok') document.getElementById('lock').style.display='none';
document.getElementById('pw').addEventListener('keydown',e=>{{ if(e.key==='Enter') check(); }});
</script>
</body></html>
"""
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"已生成 {len(results)} 隻，密碼 {WEB_PASSWORD}")
