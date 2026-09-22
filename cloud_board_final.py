import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, time, requests

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

for p in ["custom.json", "docs/custom.json"]:
    if os.path.exists(p):
        try:
            with open(p,"r",encoding="utf-8") as f:
                cj=json.load(f)
                for item in cj:
                    code=item.get("code") if isinstance(item, dict) else item
                    name=item.get("name",code) if isinstance(item, dict) else code
                    code=str(code).upper().strip()
                    if code and code not in [w[0] for w in WATCHLIST]:
                        WATCHLIST.append((code,name))
        except: pass

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
            time.sleep(0.8)
            df = tk.history(period=period, interval=interval, prepost=prepost, auto_adjust=True)
        return df, tk
    except:
        return pd.DataFrame(), None

def calc_ma(s, p):
    try:
        if len(s) < p: return 0
        return float(s.rolling(p).mean().iloc[-1])
    except:
        return 0

def calc_color_v18(d_close, d20, d60, d240, h_close, h20, h60, h240):
    if d60==0 or h20==0: return "白"
    if d_close > d60 and h_close > h60 and h_close > h240 and h240>0: return "橙"
    if d_close > d20 and h_close > h60: return "綠"
    if d_close < d20 and h_close < h20: return "藍"
    if d_close < d60 and h_close < h60: return "紅"
    return "灰"

def get_yahoo_name(tk, fallback_code, fallback_name):
    try:
        if tk is None:
            return f"{fallback_name} ({fallback_code})" if fallback_name!=fallback_code else fallback_code
        info = {}
        try:
            info = tk.info
        except:
            info = {}
        long_name = info.get('longName') or info.get('displayName') or info.get('shortName') or fallback_name
        # 清理
        long_name = str(long_name).strip()
        if not long_name or long_name.lower()=='none':
            long_name = fallback_name
        # 如果已經是 XIACY 格式，避免重複
        if fallback_code.upper() in long_name.upper():
            # 已經包含代號，就直接用 Yahoo 名，不再加括號
            # 但按用戶要求要 名稱 (代號) 格式，所以統一格式化
            # 如果 long_name 已含 (XIACY) 就保留
            if '(' in long_name and ')' in long_name:
                return long_name
            return f"{long_name} ({fallback_code})"
        else:
            return f"{long_name} ({fallback_code})"
    except:
        return f"{fallback_name} ({fallback_code})" if fallback_name!=fallback_code else fallback_code

results=[]
for code,name in WATCHLIST:
    try:
        df_day, tk = get_history(code,"1y","1d",False)
        if df_day.empty or len(df_day)<65:
            yahoo_display = get_yahoo_name(tk, code, name)
            results.append({"code":code,"name":name,"display":yahoo_display,"today":"白","yesterday":"白","pre":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None,"err":True})
            time.sleep(1.0); continue
        df_60m, _ = get_history(code,"60d","60m",True)
        if df_60m.empty:
            yahoo_display = get_yahoo_name(tk, code, name)
            results.append({"code":code,"name":name,"display":yahoo_display,"today":"白","yesterday":"白","pre":"白","curr":float(df_day['Close'].iloc[-1]),"pct":0,"d20":calc_ma(df_day['Close'],20),"d60":calc_ma(df_day['Close'],60),"d240":calc_ma(df_day['Close'],240),"h20":0,"h60":0,"h240":0,"rsi14":None,"err":True})
            time.sleep(1.0); continue
        curr = float(df_60m['Close'].iloc[-1])
        prev_close = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else curr
        pct = (curr/prev_close-1)*100 if prev_close else 0
        d_close_t = float(df_day['Close'].iloc[-1])
        d20_t = calc_ma(df_day['Close'],20); d60_t = calc_ma(df_day['Close'],60); d240_t = calc_ma(df_day['Close'],240)
        h20_t = calc_ma(df_60m['Close'],20); h60_t = calc_ma(df_60m['Close'],60); h240_t = calc_ma(df_60m['Close'],240)
        today = calc_color_v18(d_close_t, d20_t, d60_t, d240_t, curr, h20_t, h60_t, h240_t)
        df_day_y = df_day.iloc[:-1]
        d_close_y = float(df_day_y['Close'].iloc[-1])
        d20_y = calc_ma(df_day_y['Close'],20); d60_y = calc_ma(df_day_y['Close'],60); d240_y = calc_ma(df_day_y['Close'],240)
        try:
            today_date = df_day.index[-1].date()
            df_60m_y = df_60m[df_60m.index.date < today_date]
            if len(df_60m_y)<20: df_60m_y = df_60m.iloc[:-7]
            h20_y = calc_ma(df_60m_y['Close'],20); h60_y = calc_ma(df_60m_y['Close'],60); h240_y = calc_ma(df_60m_y['Close'],240)
            h_close_y = float(df_60m_y['Close'].iloc[-1]) if len(df_60m_y)>0 else d_close_y
        except:
            h20_y=h60_y=h240_y=h_close_y=d_close_y
        yesterday = calc_color_v18(d_close_y, d20_y, d60_y, d240_y, h_close_y, h20_y, h60_y, h240_y)
        try:
            df_day_pre = df_day.iloc[:-2]
            d_close_pre = float(df_day_pre['Close'].iloc[-1])
            d20_pre = calc_ma(df_day_pre['Close'],20); d60_pre = calc_ma(df_day_pre['Close'],60); d240_pre = calc_ma(df_day_pre['Close'],240)
            y_date = df_day.index[-2].date()
            df_60m_pre = df_60m[df_60m.index.date < y_date]
            if len(df_60m_pre)<20: df_60m_pre = df_60m.iloc[:-14]
            h20_pre = calc_ma(df_60m_pre['Close'],20); h60_pre = calc_ma(df_60m_pre['Close'],60); h240_pre = calc_ma(df_60m_pre['Close'],240)
            h_close_pre = float(df_60m_pre['Close'].iloc[-1]) if len(df_60m_pre)>0 else d_close_pre
            pre = calc_color_v18(d_close_pre, d20_pre, d60_pre, d240_pre, h_close_pre, h20_pre, h60_pre, h240_pre)
        except:
            pre = yesterday
        rsi14 = float(rsi(df_day['Close'],14).iloc[-1]) if len(df_day)>=15 else None
        yahoo_display = get_yahoo_name(tk, code, name)
        results.append({"code":code,"name":name,"display":yahoo_display,"today":today,"yesterday":yesterday,"pre":pre,"curr":round(curr,2),"pct":round(pct,2),"d20":round(d20_t,2),"d60":round(d60_t,2),"d240":round(d240_t,2),"h20":round(h20_t,2),"h60":round(h60_t,2),"h240":round(h240_t,2),"rsi14":rsi14,"err":False})
        time.sleep(1.0)
    except Exception as e:
        print(f"{code} err {e}")
        results.append({"code":code,"name":name,"display":f"{name} ({code})","today":"白","yesterday":"白","pre":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None,"err":True})

order={"白":-1,"灰":0,"紅":1,"藍":2,"綠":3,"橙":4}
results.sort(key=lambda x: order.get(x["today"],0), reverse=True)
hk_now = datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M:%S")
os.makedirs("docs", exist_ok=True)
with open("docs/data.json","w",encoding="utf-8") as f:
    json.dump({"update":hk_now+" 香港時間","results":results},f,ensure_ascii=False,indent=2)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
prev_path = "docs/data_prev.json"
prev_map = {}
if os.path.exists(prev_path):
    try:
        with open(prev_path,"r",encoding="utf-8") as jf:
            prev_data=json.load(jf)
            for r in prev_data.get("results",[]):
                prev_map[r["code"]]= (r.get("pre","?"), r.get("yesterday","?"), r.get("today","?"))
    except: pass

changes=[]
for r in results:
    if r["today"]=="白": continue
    cur_triple = (r["pre"], r["yesterday"], r["today"])
    prev_triple = prev_map.get(r["code"])
    if prev_triple and prev_triple != cur_triple:
        changes.append(r)

if changes and BOT_TOKEN and CHAT_ID:
    lines=[]
    for r in changes[:20]:
        prev_triple = prev_map.get(r["code"], (r["pre"], r["yesterday"], r["today"]))
        prev_str = f"{prev_triple[0]}→{prev_triple[1]}→{prev_triple[2]}"
        cur_str = f"{r['pre']}→{r['yesterday']}→{r['today']}"
        lines.append(f"{r['code']} ${r['curr']} ({r['pct']:+.2f}%)\n上次：{prev_str}\n現在：{cur_str}")
    text = f"🚀 MA變化 {hk_now}\n" + "\n\n".join(lines) + f"\n\nhttps://19moment-cloud.github.io/ma-board/"
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":text}, timeout=15)
        print(f"Telegram 發 {len(lines)}")
    except Exception as e:
        print(f"TG失敗 {e}")

with open(prev_path,"w",encoding="utf-8") as f:
    json.dump({"update":hk_now,"results":results},f,ensure_ascii=False,indent=2)

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
    dots=f"<span class='dots' data-ticker='{r['code']}' onclick='toggleDots(this)' title='點擊切換黑白'><span class='dot {r['pre']}'></span><span class='arrow'>→</span><span class='dot {r['yesterday']}'></span><span class='arrow'>→</span><span class='dot {r['today']}'></span></span>"
    rsi_html=""
    if r['rsi14'] is not None:
        if r['rsi14']>=70:
            rsi_html=f"<div class='rsi-line rsi-green'>RSI14 ({r['rsi14']:.0f})</div>"
        elif r['rsi14']<=30:
            rsi_html=f"<div class='rsi-line rsi-red'>RSI14 ({r['rsi14']:.0f})</div>"
        else:
            rsi_html=f"<div class='rsi-line'>RSI14 ({r['rsi14']:.0f})</div>"
    if is_white:
        d_row = f"<div class='ma-row'><span class='ma-w'>限流</span></div>"
        h_row = f"<div class='ma-row'><span class='ma-w'>時k含盤前後已確認</span></div>"
    else:
        d_row = f"<div class='ma-row'><span class='ma-w'>日k：</span>{ma_span_label('MA20', r['d20'], r['curr'])} {ma_span_label('MA60', r['d60'], r['curr'])} {ma_span_label('MA240', r['d240'], r['curr'])}</div>"
        h_row = f"<div class='ma-row'><span class='ma-w'>時k：</span>{ma_span_label('MA20', r['h20'], r['curr'])} {ma_span_label('MA60', r['h60'], r['curr'])} {ma_span_label('MA240', r['h240'], r['curr'])}</div>"
    display_name = r.get('display', f"{r['name']} ({r['code']})")
    cards+=f"""
<div class="card {r['today']}" data-code="{r['code'].lower()}" data-name="{display_name.lower()} {r['code'].lower()}" data-ticker="{r['code']}">
  <div class="left">
    <div class="top"><b>{display_name}</b> {dots}</div>
    <div class="mid">{curr_html} {pct_html}</div>
    {rsi_html}
    <div class="ma-box" data-ticker='{r['code']}' onclick="toggleMa(this)" title="點擊切換黑白重點觀察">{d_row}{h_row}</div>
  </div>
  <div class="star" onclick="togglePin('{r['code']}')" title="置頂">☆</div>
</div>"""

html=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MA看板 私有版</title>
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
<style>
*{{box-sizing:border-box}} body{{font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial;background:#0a0e14;color:#e6e6e6;padding:14px;margin:0}}
#lock{{position:fixed;inset:0;background:#0a0e14;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:9999}}
#lock input{{padding:14px 18px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:18px;text-align:center;margin:14px;width:240px}}
#lock button{{padding:12px 28px;border-radius:12px;border:none;background:#f59e0b;color:#000;font-weight:800;font-size:16px;cursor:pointer}}
.header{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:10px 0}} h1{{font-size:18px;margin:0}} .search{{flex:1;min-width:180px;max-width:300px;position:relative}} 
.search input{{width:100%;padding:10px 14px 10px 36px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:12px;outline:none}} .search input:focus{{border-color:#f59e0b}} .search .icon{{position:absolute;left:10px;top:50%;transform:translateY(-50%)}}
.sub{{color:#94a3b8;font-size:11px;margin-bottom:12px}}
.addRow{{display:flex;gap:8px;align-items:center;margin:0 0 12px;flex-wrap:wrap;position:relative}} .addRow input{{flex:1;min-width:200px;max-width:400px;padding:10px 14px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:12px;outline:none}} .addRow input:focus{{border-color:#f59e0b}} .addbtn{{padding:10px 16px;border-radius:12px;border:none;background:#f59e0b;color:#000;font-weight:800;cursor:pointer;white-space:nowrap}}
#yahooSuggest{{position:absolute;top:42px;left:0;width:400px;max-width:90vw;background:#1e293b;border:1px solid #334155;border-radius:12px;z-index:100;display:none;max-height:320px;overflow-y:auto}}
#yahooSuggest .s-item{{padding:10px 14px;cursor:pointer;border-bottom:1px solid #2a3441;font-size:12px;display:flex;justify-content:space-between;gap:8px}} #yahooSuggest .s-item:hover{{background:#334155}} #yahooSuggest .s-item b{{color:#fde68a}} #yahooSuggest .s-item span{{color:#94a3b8;font-size:11px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px;align-items:start;min-height:20px}}
.section{{margin-top:18px}} .section-title{{font-size:13px;color:#94a3b8;margin:0 0 8px;padding-left:4px;border-left:3px solid #f59e0b}}
.pinned-section{{margin-bottom:14px}} .pinned-title{{font-size:13px;color:#fde68a;margin:0 0 8px;display:none}} .pinned-title.show{{display:block}}
.card{{border-radius:14px;padding:11px 13px;display:flex;justify-content:space-between;align-items:flex-start;gap:10px;min-height:115px;overflow:hidden;transition:all 0.2s;position:relative;cursor:grab}} .card:active{{cursor:grabbing}} .card.hide{{display:none}} .sortable-ghost{{opacity:0.3}} .sortable-chosen{{border:2px solid #f59e0b !important}}
.橙{{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000}} .綠{{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000}} .灰{{background:#1e293b;color:#cbd5e1;border:1px solid #2a3441}} .藍{{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff}} .紅{{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff}} .白{{background:#fff;color:#000;border:2px dashed #94a3b8}}
.star{{font-size:20px;cursor:pointer;user-select:none;line-height:1;padding:2px 4px;border-radius:6px;flex-shrink:0;transition:all 0.2s}} .star.pinned{{color:#f59e0b;text-shadow:0 0 8px rgba(245,158,11,0.8)}} .card.橙 .star, .card.綠 .star{{color:#000}} .card.橙 .star.pinned, .card.綠 .star.pinned{{color:#78350f}}
.left{{flex:1;min-width:0}} .top{{font-size:12px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}} .mid{{margin-top:6px;display:flex;gap:8px;align-items:center}}
.price{{color:#facc15;font-weight:900;font-size:15px;background:rgba(0,0,0,0.32);padding:2px 8px;border-radius:6px}} .白 .price{{background:#000;color:#fff}}
.pct{{font-size:11px;font-weight:800;padding:3px 8px;border-radius:6px;background:rgba(0,0,0,0.45);color:#fff}} .pct-up{{color:#4ade80}} .pct-down{{color:#f87171}}
.dots{{display:inline-flex;align-items:center;background:#000;padding:3px 8px;border-radius:12px;gap:3px;cursor:pointer;user-select:none;border:1px solid #111;transition:all 0.2s}} .dots.white{{background:#fff !important;border-color:#ddd}} .dots .arrow{{font-size:10px;color:#fff}} .dots.white .arrow{{color:#000}} .dot{{width:9px;height:9px;border-radius:50%;display:inline-block;border:1px solid rgba(0,0,0,0.2)}} .dot.橙{{background:#ff8a00}} .dot.綠{{background:#00c853}} .dot.藍{{background:#2962ff}} .dot.紅{{background:#d50000}} .dot.灰{{background:#94a3b8}} .dot.白{{background:#fff;border:1px solid #000}}
.rsi-line{{font-size:11px;margin-top:5px;font-weight:800;padding:2px 6px;border-radius:6px;display:inline-block;background:rgba(0,0,0,0.25)}} .rsi-line.rsi-green{{color:#4ade80;border:1px solid #22c55e}} .rsi-line.rsi-red{{color:#f87171;border:1px solid #ef4444}}
.ma-box{{margin-top:6px;background:#000;border-radius:8px;padding:7px 9px;border:1px solid #111;cursor:pointer;transition:all 0.2s}} .ma-box.white{{background:#fff;border-color:#ddd}} .ma-row{{font-size:11px;line-height:1.7;display:flex;flex-wrap:wrap;gap:6px;align-items:center}} .ma-w{{color:#ffffff;font-weight:600}} .ma-box.white .ma-w{{color:#000000 !important}} .ma-item{{white-space:nowrap}} .ma-green{{color:#4ade80;font-weight:900}} .ma-red{{color:#f87171;font-weight:900}} .ma-same{{color:#ffffff}} .ma-box.white .ma-same{{color:#000}}
.pill{{padding:5px 10px;border-radius:18px;background:#1e293b;font-size:11px;margin:3px;display:inline-block;border:1px solid #334155}} .rule-box{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px;margin:14px 0;font-size:11px;line-height:1.8}} .ver{{background:#78350f;color:#fde68a;border:1px solid #92400e;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:800}}
.custom{{border:2px solid #f59e0b !important}}
</style></head><body>
<div id="lock"><h2 style="margin:0 0 8px">🔒 私有看板</h2><div style="color:#94a3b8;font-size:13px">請輸入密碼</div><input id="pw" type="password" placeholder="請輸入密碼"/><button onclick="check()">進入</button></div>

<div class="header">
<h1>🚀 MA(20/60/240) 私有版 <span class="ver">V19</span></h1>
<div class="search"><span class="icon">🔍</span><input id="search" type="text" placeholder="搜索代號/名稱模糊" /></div>
</div>
<div class="addRow"><input id="addInput" type="text" placeholder="加股：輸入 PLTR / 輸入 TS 會自動搜 Yahoo" autocomplete="off"/><div id="yahooSuggest"></div><button class="addbtn" onclick="addStock()">+ 加股</button><button class="addbtn" style="background:#1e293b;color:#fff;border:1px solid #334155" onclick="clearCustom()">清空自加</button></div>

<div class="sub">更新: {hk_now} 香港時間 | 共<span id="count">{len(results)}</span>隻 自加<span id="customCount">0</span>隻 置頂<span id="pinCount">0</span>隻 |</div>

<div class="pinned-section"><div id="pinnedTitle" class="pinned-title">⭐ 置頂觀察 (可拖動排序)</div><div id="pinnedGrid" class="grid"></div></div>

<div class="grid" id="grid">{cards}</div>

<div class="section"><div class="section-title">指數</div><div class="grid" id="grid-index"></div></div>
<div class="section"><div class="section-title">.HK</div><div class="grid" id="grid-hk"></div></div>
<div class="section"><div class="section-title">等候 (自加待建 custom.json)</div><div class="grid" id="grid-waiting"></div></div>

<div id="customGrid" class="grid" style="display:none"></div>

<div class="rule-box">
<b>技術指標MA(20，60，240)：</b><br>
🟠 股價日k站上MA60，時k站上MA60和MA240。<br>
🟢 股價日k站上MA20，時k站上MA60。<br>
🔵 股價日k跌穿MA20，時k跌穿MA20。<br>
🔴 股價日k跌穿MA60，時k跌穿MA60。<br>
⚪ 不符合以上條件。<br>
⬜ 白=限流 ⭐ 點星星置頂，卡片可拖動到任意分類<br><br>
<button onclick="exportCustom()" style="padding:8px 14px;border-radius:8px;border:none;background:#f59e0b;color:#000;font-weight:800;cursor:pointer">📋 匯出自加清單 (給我加到雲端)</button>
</div>

<script>
const REAL_PW="{WEB_PASSWORD}";
function check(){{const v=document.getElementById('pw').value;if(v===REAL_PW){{document.getElementById('lock').style.display='none';sessionStorage.setItem('ma_pw','ok');}}else{{alert('密碼錯誤');}}}}
if(sessionStorage.getItem('ma_pw')==='ok')document.getElementById('lock').style.display='none';
document.getElementById('pw').addEventListener('keydown',e=>{{if(e.key==='Enter')check();}});

let focusDots = JSON.parse(localStorage.getItem('focusDotsV19')||localStorage.getItem('focusDotsV18')||'{{}}');
let focusMa = JSON.parse(localStorage.getItem('focusMaV19')||localStorage.getItem('focusMaV18')||'{{}}');
function toggleDots(el){{ el.classList.toggle('white'); let t=el.getAttribute('data-ticker'); if(t){{ if(el.classList.contains('white')) focusDots[t]=1; else delete focusDots[t]; localStorage.setItem('focusDotsV19', JSON.stringify(focusDots)); }} }}
function toggleMa(el){{ el.classList.toggle('white'); let t=el.getAttribute('data-ticker'); if(t){{ if(el.classList.contains('white')) focusMa[t]=1; else delete focusMa[t]; localStorage.setItem('focusMaV19', JSON.stringify(focusMa)); }} }}
function applyFocus(){{ document.querySelectorAll('.dots[data-ticker]').forEach(el=>{{ let t=el.getAttribute('data-ticker'); if(focusDots[t]) el.classList.add('white'); }}); document.querySelectorAll('.ma-box[data-ticker]').forEach(el=>{{ let t=el.getAttribute('data-ticker'); if(focusMa[t]) el.classList.add('white'); }}); }}

// 拖動排序
let layoutOrder = JSON.parse(localStorage.getItem('layoutOrderV19')||'{{}}');
function saveLayout(){{
  let order={{}};
  ['grid','pinnedGrid','grid-index','grid-hk','grid-waiting'].forEach(id=>{{
    let el=document.getElementById(id);
    if(!el) return;
    order[id]=Array.from(el.children).map(c=>c.getAttribute('data-ticker')).filter(Boolean);
  }});
  localStorage.setItem('layoutOrderV19', JSON.stringify(order));
}}
function initSortable(){{
  ['grid','pinnedGrid','grid-index','grid-hk','grid-waiting'].forEach(id=>{{
    let el=document.getElementById(id);
    if(!el) return;
    new Sortable(el, {{
      group: 'shared',
      animation: 150,
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      handle: '.card',
      onEnd: function(){{ saveLayout(); updateCounts(); }}
    }});
  }});
}}
function restoreLayout(){{
  try{{
    let order=JSON.parse(localStorage.getItem('layoutOrderV19')||'{{}}');
    Object.keys(order).forEach(gridId=>{{
      let grid=document.getElementById(gridId);
      if(!grid) return;
      let tickerMap={{}};
      // 收集所有卡片
      document.querySelectorAll('.card').forEach(c=>{{ let t=c.getAttribute('data-ticker'); if(t) tickerMap[t.toUpperCase()]=c; }});
      // 按保存順序重排
      order[gridId].forEach(ticker=>{{
        let card=tickerMap[ticker.toUpperCase()];
        if(card && grid.contains(card)==false) grid.appendChild(card);
        else if(card && order[gridId].indexOf(ticker)!== Array.from(grid.children).indexOf(card)) grid.appendChild(card);
      }});
    }});
  }}catch(e){{}}
}}
function updateCounts(){{
  document.getElementById('pinCount').innerText=document.getElementById('pinnedGrid').children.length;
}}

let pinnedStocks = JSON.parse(localStorage.getItem('pinnedV19')||localStorage.getItem('pinnedV18')||'[]');
function isPinned(t){{ return pinnedStocks.includes(t); }}
function togglePin(ticker){{
  ticker=ticker.toUpperCase();
  if(isPinned(ticker)) pinnedStocks=pinnedStocks.filter(t=>t!==ticker);
  else pinnedStocks.push(ticker);
  localStorage.setItem('pinnedV19', JSON.stringify(pinnedStocks));
  // 移動到置頂區或移回默認
  let card=document.querySelector(`.card[data-ticker="${{ticker}}"]`);
  if(!card) card=document.querySelector(`[data-ticker="${{ticker}}"].card`);
  if(card){{
    if(isPinned(ticker)) document.getElementById('pinnedGrid').appendChild(card);
    else document.getElementById('grid').appendChild(card);
  }}
  renderPins(); saveLayout(); applyFocus();
}}
function renderPins(){{
  const pinnedTitle=document.getElementById('pinnedTitle');
  let count=document.getElementById('pinnedGrid').children.length;
  if(count>0) pinnedTitle.classList.add('show'); else pinnedTitle.classList.remove('show');
  document.getElementById('pinCount').innerText=count;
  document.querySelectorAll('.card').forEach(card=>{{ let t=(card.getAttribute('data-ticker')||'').toUpperCase(); let star=card.querySelector('.star'); if(!star) return; if(pinnedStocks.includes(t)){{ star.innerText='★'; star.classList.add('pinned'); }} else{{ star.innerText='☆'; star.classList.remove('pinned'); }} }});
}}

const searchInput=document.getElementById('search');
function doSearch(q){{ q=q.trim().toLowerCase(); document.querySelectorAll('.grid .card').forEach(card=>{{ const code=card.getAttribute('data-code')||''; const name=card.getAttribute('data-name')||''; if(!q) card.classList.remove('hide'); else{{ if(code.includes(q)||name.includes(q)) card.classList.remove('hide'); else card.classList.add('hide'); }} }}); }}
searchInput.addEventListener('input', e=>doSearch(e.target.value));

let customStocks = JSON.parse(localStorage.getItem('customStocksV19')||localStorage.getItem('customStocksV18')||'[]');
function saveCustom(){{ localStorage.setItem('customStocksV19', JSON.stringify(customStocks)); document.getElementById('customCount').innerText=customStocks.length; document.getElementById('count').innerText = {len(results)} + customStocks.length; }}
function clearCustom(){{ if(!confirm('清空所有自加？')) return; customStocks=[]; saveCustom(); document.getElementById('grid-waiting').innerHTML=''; saveLayout(); }}
function exportCustom(){{ if(customStocks.length===0){{ alert('還沒有自加股票'); return; }} let jsonArr=customStocks.map(s=>({{code:s.code, name:s.name}})); let txt=JSON.stringify(jsonArr, null, 2); navigator.clipboard.writeText(txt).then(()=>alert('已複製 custom.json！\\n在 GitHub 根目錄新建 custom.json 貼上，5分鐘後雲端自動有數據\\n\\n'+txt)).catch(()=>prompt('複製這段，新建 custom.json：', txt)); }}
function normalizeTicker(input){{ input=input.trim().toUpperCase(); if(!input) return null; if(/^\\d{{3,5}}$/.test(input)) return input+'.HK'; return input; }}

async function addStock(input){{ 
  let raw=(input||document.getElementById('addInput').value||'').trim();
  if(!raw) return;
  let firstToken=raw.split(/[\\s,，]+/)[0];
  let ticker=normalizeTicker(firstToken);
  let name=raw.replace(firstToken,'').trim()||firstToken;
  document.getElementById('addInput').value='';
  document.getElementById('yahooSuggest').style.display='none';
  if(customStocks.find(s=>s.code===ticker)){{ alert(ticker+' 已加過'); return; }}
  customStocks.push({{code:ticker, name:name}});
  saveCustom();
  let cardId='custom-'+ticker.replace(/\\./g,'-');
  let waitingGrid=document.getElementById('grid-waiting');
  waitingGrid.insertAdjacentHTML('beforeend', `<div class="card 白 custom" id="${{cardId}}" data-code="${{ticker.toLowerCase()}}" data-name="${{name.toLowerCase()}} ${{ticker.toLowerCase()}}" data-ticker="${{ticker}}"><div class="left"><div class="top"><b>${{ticker}}</b> ${{name}} (${{ticker}}) <span class="dots" data-ticker="${{ticker}}" onclick="toggleDots(this)"><span class="dot 白"></span><span class="arrow">→</span><span class="dot 白"></span><span class="arrow">→</span><span class="dot 白"></span></span> <span style="font-size:10px;cursor:pointer" onclick="removeCustom('${{ticker}}')">❌</span></div><div class="mid"><span class="price">已加入等候區</span> <span class="pct">點匯出建custom.json後5分有數據</span></div><div class="ma-box" data-ticker="${{ticker}}" onclick="toggleMa(this)"><div class="ma-row"><span class="ma-w">已保存到等候區，匯出後雲端自動算</span></div></div></div><div class="star" onclick="togglePin('${{ticker}}')">☆</div></div>`);
  saveLayout(); applyFocus();
  try{{ let resp=await fetch('data.json'); let j=await resp.json(); let found=j.results.find(r=>r.code.toUpperCase()===ticker.toUpperCase()); if(found){{ let r=found; let card=document.getElementById(cardId); if(card){{ let display=r.display||`${{r.name}} (${{r.code}})`; let pctCls=r.pct>=0?'pct-up':'pct-down'; let sign=r.pct>=0?'+':''; let dots=`<span class="dots ${{focusDots[r.code]?'white':''}}" data-ticker="${{r.code}}" onclick="toggleDots(this)"><span class="dot ${{r.pre}}"></span><span class="arrow">→</span><span class="dot ${{r.yesterday}}"></span><span class="arrow">→</span><span class="dot ${{r.today}}"></span></span>`; let rsiHtml=''; if(r.rsi14!=null){{ if(r.rsi14>=70) rsiHtml=`<div class='rsi-line rsi-green'>RSI14 (${{r.rsi14.toFixed(0)}})</div>`; else if(r.rsi14<=30) rsiHtml=`<div class='rsi-line rsi-red'>RSI14 (${{r.rsi14.toFixed(0)}})</div>`; else rsiHtml=`<div class='rsi-line'>RSI14 (${{r.rsi14.toFixed(0)}})</div>`; }} let maLabel=(label,val,curr)=>{{ if(!val) return `<span class='ma-item'><span class='ma-w'>${{label}}(--)</span></span>`; let cls=val>curr?'ma-red':'ma-green'; return `<span class='ma-item'><span class='ma-w'>${{label}}</span><span class='${{cls}}'>(${{val.toFixed(0)}})</span></span>`; }}; let dRow=`<div class='ma-row'><span class='ma-w'>日k：</span>${{maLabel('MA20',r.d20,r.curr)}} ${{maLabel('MA60',r.d60,r.curr)}} ${{maLabel('MA240',r.d240,r.curr)}}</div>`; let hRow=`<div class='ma-row'><span class='ma-w'>時k：</span>${{maLabel('MA20',r.h20,r.curr)}} ${{maLabel('MA60',r.h60,r.curr)}} ${{maLabel('MA240',r.h240,r.curr)}}</div>`; let newHtml=`<div class="card ${{r.today}} custom" id="${{cardId}}" data-code="${{r.code.toLowerCase()}}" data-name="${{display.toLowerCase()}} ${{r.code.toLowerCase()}}" data-ticker="${{r.code}}"><div class="left"><div class="top"><b>${{display}}</b> ${{dots}} <span style="font-size:10px;cursor:pointer" onclick="removeCustom('${{r.code}}')">❌</span></div><div class="mid"><span class="price">$${{r.curr}}</span> <span class="pct ${{pctCls}}">${{sign}}${{r.pct.toFixed(2)}}%</span></div>${{rsiHtml}}<div class="ma-box ${{focusMa[r.code]?'white':''}}" data-ticker="${{r.code}}" onclick="toggleMa(this)">${{dRow}}${{hRow}}</div></div><div class="star" onclick="togglePin('${{r.code}}')">☆</div></div>`; card.outerHTML=newHtml; document.getElementById('grid').appendChild(document.getElementById(cardId)); saveLayout(); applyFocus(); }} }}catch(e){{}}
}}

function removeCustom(ticker){{ customStocks=customStocks.filter(s=>s.code!==ticker.toUpperCase()); localStorage.setItem('customStocksV19',JSON.stringify(customStocks)); delete focusDots[ticker.toUpperCase()]; delete focusMa[ticker.toUpperCase()]; localStorage.setItem('focusDotsV19', JSON.stringify(focusDots)); localStorage.setItem('focusMaV19', JSON.stringify(focusMa)); pinnedStocks=pinnedStocks.filter(s=>s!==ticker.toUpperCase()); localStorage.setItem('pinnedV19',JSON.stringify(pinnedStocks)); saveCustom(); let el=document.getElementById('custom-'+ticker.replace(/\\./g,'-')); if(!el) el=document.querySelector(`[data-ticker="${{ticker}}"]`); if(el) el.remove(); saveLayout(); renderPins(); }}

document.getElementById('addInput').addEventListener('keydown', e=>{{ if(e.key==='Enter'){{ let suggest=document.getElementById('yahooSuggest'); if(suggest.style.display!=='none' && suggest.firstChild){{ suggest.firstChild.click(); }} else addStock(); }} }});

// Yahoo 搜索
let yahooTimer=null;
document.getElementById('addInput').addEventListener('input', e=>{{
  let q=e.target.value.trim();
  let box=document.getElementById('yahooSuggest');
  if(!q || q.length<1){{ box.style.display='none'; return; }}
  clearTimeout(yahooTimer);
  yahooTimer=setTimeout(async ()=>{{
    try{{
      let url=`https://query1.finance.yahoo.com/v1/finance/search?q=${{encodeURIComponent(q)}}&quotesCount=10&newsCount=0`;
      let resp=await fetch(url);
      if(!resp.ok) throw 'fail';
      let data=await resp.json();
      let quotes=data.quotes||[];
      if(quotes.length==0){{ box.style.display='none'; return; }}
      box.innerHTML='';
      quotes.forEach(item=>{{
        let sym=item.symbol;
        let name=item.shortname||item.longname||sym;
        let exch=item.exchange||'';
        let div=document.createElement('div');
        div.className='s-item';
        div.innerHTML=`<span><b>${{sym}}</b> ${{name}}</span><span>${{exch}}</span>`;
        div.onclick=()=>{{
          document.getElementById('addInput').value=sym+' '+name;
          box.style.display='none';
          addStock(sym+' '+name);
        }};
        box.appendChild(div);
      }});
      box.style.display='block';
    }}catch(err){{
      // 備用接口
      try{{
        let url2=`https://autoc.finance.yahoo.com/autoc?query=${{encodeURIComponent(q)}}&region=1&lang=en-US`;
        let r2=await fetch(url2);
        let d2=await r2.json();
        let results=d2.ResultSet?.Result||[];
        let box2=document.getElementById('yahooSuggest');
        box2.innerHTML='';
        results.slice(0,10).forEach(item=>{{
          let sym=item.symbol;
          let name=item.name||sym;
          let div=document.createElement('div');
          div.className='s-item';
          div.innerHTML=`<span><b>${{sym}}</b> ${{name}}</span><span>${{item.exch||''}}</span>`;
          div.onclick=()=>{{ document.getElementById('addInput').value=sym+' '+name; box2.style.display='none'; addStock(sym+' '+name); }};
          box2.appendChild(div);
        }});
        box2.style.display= results.length? 'block':'none';
      }}catch(e2){{ box.style.display='none'; }}
    }}
  }}, 300);
}});
document.addEventListener('click', e=>{{ if(!e.target.closest('.addRow')) document.getElementById('yahooSuggest').style.display='none'; }});

(function(){{ 
  saveCustom();
  // 自加卡片先進等候區
  customStocks.forEach(s=>{{
    let cardId='custom-'+s.code.replace(/\\./g,'-');
    if(document.getElementById(cardId)) return;
    document.getElementById('grid-waiting').insertAdjacentHTML('beforeend', `<div class="card 白 custom" id="${{cardId}}" data-code="${{s.code.toLowerCase()}}" data-name="${{s.name.toLowerCase()}} ${{s.code.toLowerCase()}}" data-ticker="${{s.code}}"><div class="left"><div class="top"><b>${{s.code}}</b> ${{s.name}} (${{s.code}}) <span class="dots" data-ticker="${{s.code}}" onclick="toggleDots(this)"><span class="dot 白"></span><span class="arrow">→</span><span class="dot 白"></span><span class="arrow">→</span><span class="dot 白"></span></span> <span style="font-size:10px;cursor:pointer" onclick="removeCustom('${{s.code}}')">❌</span></div><div class="mid"><span class="price">已加入等候區</span> <span class="pct">點匯出建custom.json後5分有數據</span></div><div class="ma-box" data-ticker="${{s.code}}" onclick="toggleMa(this)"><div class="ma-row"><span class="ma-w">等候區，匯出後雲端自動算</span></div></div></div><div class="star" onclick="togglePin('${{s.code}}')">☆</div></div>`);
  }});
  // 嘗試匹配 data.json 中已有數據的自加
  fetch('data.json').then(r=>r.json()).then(j=>{{
    j.results.forEach(r=>{{
      let card=document.getElementById('custom-'+r.code.replace(/\\./g,'-'));
      if(card){{ 
        let display=r.display||`${{r.name}} (${{r.code}})`;
        let pctCls=r.pct>=0?'pct-up':'pct-down'; let sign=r.pct>=0?'+':'';
        let dots=`<span class="dots ${{focusDots[r.code]?'white':''}}" data-ticker="${{r.code}}" onclick="toggleDots(this)"><span class="dot ${{r.pre}}"></span><span class="arrow">→</span><span class="dot ${{r.yesterday}}"></span><span class="arrow">→</span><span class="dot ${{r.today}}"></span></span>`;
        let rsiHtml=''; if(r.rsi14!=null){{ if(r.rsi14>=70) rsiHtml=`<div class='rsi-line rsi-green'>RSI14 (${{r.rsi14.toFixed(0)}})</div>`; else if(r.rsi14<=30) rsiHtml=`<div class='rsi-line rsi-red'>RSI14 (${{r.rsi14.toFixed(0)}})</div>`; else rsiHtml=`<div class='rsi-line'>RSI14 (${{r.rsi14.toFixed(0)}})</div>`; }}
        let maLabel=(label,val,curr)=>{{ if(!val) return `<span class='ma-item'><span class='ma-w'>${{label}}(--)</span></span>`; let cls=val>curr?'ma-red':'ma-green'; return `<span class='ma-item'><span class='ma-w'>${{label}}</span><span class='${{cls}}'>(${{val.toFixed(0)}})</span></span>`; }};
        let dRow=`<div class='ma-row'><span class='ma-w'>日k：</span>${{maLabel('MA20',r.d20,r.curr)}} ${{maLabel('MA60',r.d60,r.curr)}} ${{maLabel('MA240',r.d240,r.curr)}}</div>`;
        let hRow=`<div class='ma-row'><span class='ma-w'>時k：</span>${{maLabel('MA20',r.h20,r.curr)}} ${{maLabel('MA60',r.h60,r.curr)}} ${{maLabel('MA240',r.h240,r.curr)}}</div>`;
        card.outerHTML=`<div class="card ${{r.today}} custom" id="custom-${{r.code.replace(/\\./g,'-')}}" data-code="${{r.code.toLowerCase()}}" data-name="${{display.toLowerCase()}} ${{r.code.toLowerCase()}}" data-ticker="${{r.code}}"><div class="left"><div class="top"><b>${{display}}</b> ${{dots}} <span style="font-size:10px;cursor:pointer" onclick="removeCustom('${{r.code}}')">❌</span></div><div class="mid"><span class="price">$${{r.curr}}</span> <span class="pct ${{pctCls}}">${{sign}}${{r.pct.toFixed(2)}}%</span></div>${{rsiHtml}}<div class="ma-box ${{focusMa[r.code]?'white':''}}" data-ticker="${{r.code}}" onclick="toggleMa(this)">${{dRow}}${{hRow}}</div></div><div class="star ${{isPinned(r.code)?'pinned':''}}" onclick="togglePin('${{r.code}}')">${{isPinned(r.code)?'★':'☆'}}</div></div>`;
      }}
    }});
    restoreLayout(); initSortable(); renderPins(); applyFocus(); saveLayout();
  }});
  initSortable(); restoreLayout(); renderPins(); applyFocus();
}})();
</script>
</body></html>
"""
with open("docs/index.html","w",encoding="utf-8") as f:
    f.write(html)
print("V19 已生成")
