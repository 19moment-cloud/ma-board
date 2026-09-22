import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, time, requests, re

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

def calc_color(d_close, d20, d60, d240, h_close, h20, h60, h240):
    if d60==0 or h20==0: return "白"
    if d_close > d60 and h_close > h60 and h_close > h240 and h240>0: return "橙"
    if d_close > d20 and h_close > h60: return "綠"
    if d_close < d20 and h_close < h20: return "藍"
    if d_close < d60 and h_close < h60: return "紅"
    return "灰"

def get_hk_yahoo_name(ticker, fallback_name):
    """優先用香港 Yahoo 財經的中文名"""
    try:
        # 1. 先試 HK Yahoo 頁面抓標題
        if ".HK" in ticker.upper() or ticker.upper() in ["XIACY","BABA","BIDU","NIO","LI","XPEV","FUTU"]:
            # 對於中概股，嘗試 HK 頁面
            hk_ticker = ticker
            # XIACY 對應 01810.HK 小米
            map_hk = {"XIACY":"01810.HK","BABA":"09988.HK","BIDU":"09888.HK","NIO":"09866.HK","LI":"02015.HK","XPEV":"09868.HK","FUTU":""}
            if ticker.upper() in map_hk and map_hk[ticker.upper()]:
                hk_ticker = map_hk[ticker.upper()]
            try:
                url = f"https://hk.finance.yahoo.com/quote/{hk_ticker}"
                headers = {"User-Agent":"Mozilla/5.0"}
                r = requests.get(url, headers=headers, timeout=8)
                if r.status_code==200:
                    # 標題通常是 小米集團-W (01810.HK) - ...
                    m = re.search(r'<title>(.*?)\(', r.text)
                    if m:
                        name = m.group(1).strip()
                        # 清理 - Yahoo
                        name = name.replace(" - Yahoo 財經","").strip()
                        if name and len(name)>1:
                            return name
            except:
                pass
        # 2. 回退 yfinance longName
        return fallback_name
    except:
        return fallback_name

def get_yahoo_name(tk, code, fallback):
    try:
        info = {}
        try: info = tk.info
        except: info = {}
        long_name = info.get('longName') or info.get('displayName') or info.get('shortName') or fallback
        long_name = str(long_name).strip()
        if not long_name or long_name.lower()=='none':
            long_name = fallback
        # 嘗試香港名
        hk_name = get_hk_yahoo_name(code, long_name)
        return hk_name
    except:
        return fallback

def format_display(code, name):
    """ (代號)名稱，總長度最多35位 """
    # 去掉括號內已有代號的情況
    clean_name = name
    # 如果 name 已包含 (CODE) 去掉
    clean_name = re.sub(r'\s*\(.*?\)\s*', '', clean_name).strip()
    if not clean_name:
        clean_name = code
    full = f"({code}){clean_name}"
    if len(full) > 35:
        # 截斷名稱部分
        remain = 35 - len(f"({code})")
        clean_name = clean_name[:max(0,remain-1)] + "…" if remain>2 else ""
        full = f"({code}){clean_name}"
        if len(full)>35:
            full = full[:35]
    return full

results=[]
for code,name in WATCHLIST:
    try:
        df_day, tk = get_history(code,"1y","1d",False)
        yahoo_raw_name = get_yahoo_name(tk, code, name)
        display = format_display(code, yahoo_raw_name)
        if df_day.empty or len(df_day)<65:
            results.append({"code":code,"name":name,"display":display,"raw_name":yahoo_raw_name,"today":"白","yesterday":"白","pre":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None})
            time.sleep(1.0); continue
        df_60m, _ = get_history(code,"60d","60m",True)
        if df_60m.empty:
            results.append({"code":code,"name":name,"display":display,"raw_name":yahoo_raw_name,"today":"白","yesterday":"白","pre":"白","curr":float(df_day['Close'].iloc[-1]),"pct":0,"d20":calc_ma(df_day['Close'],20),"d60":calc_ma(df_day['Close'],60),"d240":calc_ma(df_day['Close'],240),"h20":0,"h60":0,"h240":0,"rsi14":None})
            time.sleep(1.0); continue
        curr = float(df_60m['Close'].iloc[-1])
        prev_close = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else curr
        pct = (curr/prev_close-1)*100 if prev_close else 0
        d_close_t = float(df_day['Close'].iloc[-1])
        d20_t = calc_ma(df_day['Close'],20); d60_t = calc_ma(df_day['Close'],60); d240_t = calc_ma(df_day['Close'],240)
        h20_t = calc_ma(df_60m['Close'],20); h60_t = calc_ma(df_60m['Close'],60); h240_t = calc_ma(df_60m['Close'],240)
        today = calc_color(d_close_t, d20_t, d60_t, d240_t, curr, h20_t, h60_t, h240_t)
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
        yesterday = calc_color(d_close_y, d20_y, d60_y, d240_y, h_close_y, h20_y, h60_y, h240_y)
        try:
            df_day_pre = df_day.iloc[:-2]
            d_close_pre = float(df_day_pre['Close'].iloc[-1])
            d20_pre = calc_ma(df_day_pre['Close'],20); d60_pre = calc_ma(df_day_pre['Close'],60); d240_pre = calc_ma(df_day_pre['Close'],240)
            y_date = df_day.index[-2].date()
            df_60m_pre = df_60m[df_60m.index.date < y_date]
            if len(df_60m_pre)<20: df_60m_pre = df_60m.iloc[:-14]
            h20_pre = calc_ma(df_60m_pre['Close'],20); h60_pre = calc_ma(df_60m_pre['Close'],60); h240_pre = calc_ma(df_60m_pre['Close'],240)
            h_close_pre = float(df_60m_pre['Close'].iloc[-1]) if len(df_60m_pre)>0 else d_close_pre
            pre = calc_color(d_close_pre, d20_pre, d60_pre, d240_pre, h_close_pre, h20_pre, h60_pre, h240_pre)
        except:
            pre = yesterday
        rsi14 = float(rsi(df_day['Close'],14).iloc[-1]) if len(df_day)>=15 else None
        results.append({"code":code,"name":name,"display":display,"raw_name":yahoo_raw_name,"today":today,"yesterday":yesterday,"pre":pre,"curr":round(curr,2),"pct":round(pct,2),"d20":round(d20_t,2),"d60":round(d60_t,2),"d240":round(d240_t,2),"h20":round(h20_t,2),"h60":round(h60_t,2),"h240":round(h240_t,2),"rsi14":rsi14})
        time.sleep(1.0)
    except Exception as e:
        print(f"{code} err {e}")
        results.append({"code":code,"name":name,"display":format_display(code,name),"raw_name":name,"today":"白","yesterday":"白","pre":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None})

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
        for r in json.load(open(prev_path,"r",encoding="utf-8")).get("results",[]):
            prev_map[r["code"]]= (r.get("pre","?"), r.get("yesterday","?"), r.get("today","?"))
    except: pass
changes=[]
for r in results:
    if r["today"]=="白": continue
    cur=(r["pre"], r["yesterday"], r["today"])
    prev=prev_map.get(r["code"])
    if prev and prev!=cur: changes.append(r)
if changes and BOT_TOKEN and CHAT_ID:
    lines=[]
    for r in changes[:20]:
        prev=prev_map.get(r["code"], (r["pre"], r["yesterday"], r["today"]))
        lines.append(f"{r['code']} ${r['curr']} ({r['pct']:+.2f}%)\n上次：{prev[0]}→{prev[1]}→{prev[2]}\n現在：{r['pre']}→{r['yesterday']}→{r['today']}")
    text=f"🚀 MA變化 {hk_now}\n" + "\n\n".join(lines) + f"\n\nhttps://19moment-cloud.github.io/ma-board/"
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":text}, timeout=15)
    except: pass
with open(prev_path,"w",encoding="utf-8") as f:
    json.dump({"update":hk_now,"results":results},f,ensure_ascii=False,indent=2)

def ma_span(label, val, curr):
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
    dots=f"<span class='dots' data-ticker='{r['code']}'><span class='dot {r['pre']}'></span><span class='arrow'>→</span><span class='dot {r['yesterday']}'></span><span class='arrow'>→</span><span class='dot {r['today']}'></span></span>"
    rsi_html=""
    if r.get('rsi14') is not None:
        v=r['rsi14']
        cls = "rsi-green" if v>=70 else "rsi-red" if v<=30 else ""
        rsi_html=f"<span class='rsi-inline {cls}'>RSI14 ({v:.0f})</span>"
    if is_white:
        d_row = f"<div class='ma-row'><span class='ma-w'>限流</span></div>"
        h_row = f"<div class='ma-row'><span class='ma-w'>時k含盤前後已確認</span></div>"
    else:
        d_row = f"<div class='ma-row'><span class='ma-w'>日k：</span>{ma_span('MA20', r['d20'], r['curr'])} {ma_span('MA60', r['d60'], r['curr'])} {ma_span('MA240', r['d240'], r['curr'])}</div>"
        h_row = f"<div class='ma-row'><span class='ma-w'>時k：</span>{ma_span('MA20', r['h20'], r['curr'])} {ma_span('MA60', r['h60'], r['curr'])} {ma_span('MA240', r['h240'], r['curr'])}</div>"
    display = r.get('display', f"({r['code']}){r['name']}")
    cards+=f"""
<div class="card {r['today']}" data-code="{r['code'].lower()}" data-name="{display.lower()} {r['code'].lower()}" data-ticker="{r['code']}">
  <div class="left">
    <div class="top"><b>{display}</b> {dots}</div>
    <div class="mid">{curr_html} {pct_html} {rsi_html}</div>
    <div class="ma-box" data-ticker='{r['code']}'><div class="ma-inner">{d_row}{h_row}</div></div>
  </div>
  <div class="star" data-pin='{r['code']}'>☆</div>
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
#yahooSuggest{{position:absolute;top:42px;left:0;width:420px;max-width:90vw;background:#1e293b;border:1px solid #334155;border-radius:12px;z-index:200;display:none;max-height:360px;overflow-y:auto;box-shadow:0 10px 30px rgba(0,0,0,0.5)}}
#yahooSuggest .s-item{{padding:10px 14px;cursor:pointer;border-bottom:1px solid #2a3441;font-size:12px;display:flex;justify-content:space-between;gap:8px}} #yahooSuggest .s-item:hover{{background:#334155}} #yahooSuggest .s-item b{{color:#fde68a}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px;align-items:start;min-height:20px}}
.section{{margin-top:18px}} .section-title{{font-size:13px;color:#94a3b8;margin:0 0 8px;padding-left:4px;border-left:3px solid #f59e0b}}
.pinned-section{{margin-bottom:14px}} .pinned-title{{font-size:13px;color:#fde68a;margin:0 0 8px;display:none}} .pinned-title.show{{display:block}}
.card{{border-radius:14px;padding:11px 13px;display:flex;justify-content:space-between;align-items:flex-start;gap:10px;min-height:115px;overflow:hidden;position:relative;cursor:grab}} .card.hide{{display:none}} .sortable-ghost{{opacity:0.3}} .sortable-chosen{{border:2px solid #f59e0b !important}}
.橙{{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000}} .綠{{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000}} .灰{{background:#1e293b;color:#cbd5e1;border:1px solid #2a3441}} .藍{{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff}} .紅{{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff}} .白{{background:#fff;color:#000;border:2px dashed #94a3b8}}
.star{{font-size:20px;cursor:pointer;user-select:none;line-height:1;padding:2px 4px;border-radius:6px;flex-shrink:0}} .star.pinned{{color:#f59e0b}} 
.left{{flex:1;min-width:0}} .top{{font-size:12px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}} .top b{{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block}} .mid{{margin-top:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.price{{color:#facc15;font-weight:900;font-size:15px;background:rgba(0,0,0,0.32);padding:2px 8px;border-radius:6px}} .白 .price{{background:#000;color:#fff}}
.pct{{font-size:11px;font-weight:800;padding:3px 8px;border-radius:6px;background:rgba(0,0,0,0.45);color:#fff}} .pct-up{{color:#4ade80}} .pct-down{{color:#f87171}}
.dots{{display:inline-flex;align-items:center;background:#000;padding:3px 8px;border-radius:12px;gap:3px;cursor:pointer;user-select:none;border:1px solid #111}} .dots.white{{background:#fff !important;border-color:#ddd}} .dots .arrow{{font-size:10px;color:#fff}} .dots.white .arrow{{color:#000}} .dot{{width:9px;height:9px;border-radius:50%;display:inline-block}} .dot.橙{{background:#ff8a00}} .dot.綠{{background:#00c853}} .dot.藍{{background:#2962ff}} .dot.紅{{background:#d50000}} .dot.灰{{background:#94a3b8}} .dot.白{{background:#fff;border:1px solid #000}}
.rsi-inline{{font-size:11px;font-weight:800;padding:3px 7px;border-radius:6px;background:rgba(0,0,0,0.35);margin-left:2px}} .rsi-inline.rsi-green{{color:#4ade80;border:1px solid #22c55e}} .rsi-inline.rsi-red{{color:#f87171;border:1px solid #ef4444}}
.ma-box{{margin-top:6px;background:#000;border-radius:8px;padding:7px 9px;border:1px solid #111;cursor:pointer}} .ma-box.white{{background:#fff;border-color:#ddd}} .ma-row{{font-size:11px;line-height:1.7;display:flex;flex-wrap:wrap;gap:6px}} .ma-w{{color:#fff;font-weight:600}} .ma-box.white .ma-w{{color:#000 !important}} .ma-item{{white-space:nowrap}} .ma-green{{color:#4ade80;font-weight:900}} .ma-red{{color:#f87171;font-weight:900}} .ma-same{{color:#fff}} .ma-box.white .ma-same{{color:#000}}
.pill{{padding:5px 10px;border-radius:18px;background:#1e293b;font-size:11px;margin:3px;display:inline-block;border:1px solid #334155}} .rule-box{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px;margin:14px 0;font-size:11px;line-height:1.8}} .ver{{background:#78350f;color:#fde68a;border:1px solid #92400e;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:800}}
</style></head><body>
<div id="lock"><h2>🔒 私有看板</h2><div style="color:#94a3b8;font-size:13px">請輸入密碼</div><input id="pw" type="password" placeholder="請輸入密碼" autocomplete="off"/><button id="enterBtn" type="button">進入</button><div id="lockMsg" style="color:#f87171;font-size:12px;margin-top:8px"></div></div>

<div class="header">
<h1><a href="https://hk.finance.yahoo.com/markets" target="_blank" style="text-decoration:none" title="開 Yahoo HK 行情">🚀</a> MA(20/60/240) 私有版 <span class="ver">V20.2</span></h1>
<div class="search"><span class="icon">🔍</span><input id="search" type="text" placeholder="搜索代號/名稱模糊" /></div>
</div>
<div class="addRow"><input id="addInput" type="text" placeholder="加股：輸入 TS 自動搜 Yahoo HK" autocomplete="off"/><div id="yahooSuggest"></div><button class="addbtn" id="addBtn">+ 加股</button><button class="addbtn" id="clearBtn" style="background:#1e293b;color:#fff;border:1px solid #334155">清空自加</button></div>

<div class="sub">更新: {hk_now} 香港時間 | 共<span id="count">{len(results)}</span>隻 自加<span id="customCount">0</span>隻 置頂<span id="pinCount">0</span>隻 |</div>

<div class="pinned-section"><div id="pinnedTitle" class="pinned-title">⭐ 置頂觀察 (可拖動排序)</div><div id="pinnedGrid" class="grid"></div></div>

<div class="grid" id="grid">{cards}</div>

<div class="section"><div class="section-title">.HK</div><div class="grid" id="grid-hk"></div></div>
<div class="section"><div class="section-title">指數</div><div class="grid" id="grid-index"></div></div>
<div class="section"><div class="section-title">等候 (自加待建 custom.json)</div><div class="grid" id="grid-waiting"></div></div>

<div class="rule-box">
<b>技術指標MA(20，60，240)：</b><br>
🟠 股價日k站上MA60，時k站上MA60和MA240。<br>
🟢 股價日k站上MA20，時k站上MA60。<br>
🔵 股價日k跌穿MA20，時k跌穿MA20。<br>
🔴 股價日k跌穿MA60，時k跌穿MA60。<br>
⚪ 不符合以上條件。<br>
⬜ 白=限流 ⭐ 點星星置頂，卡片可拖動<br><br>
<button id="exportBtn" style="padding:8px 14px;border-radius:8px;border:none;background:#f59e0b;color:#000;font-weight:800;cursor:pointer">📋 匯出自加清單</button>
</div>

<script>
(function(){{
  const REAL_PW="{WEB_PASSWORD}";
  function unlock(){{ const v=document.getElementById('pw').value.trim(); if(v===REAL_PW){{ document.getElementById('lock').style.display='none'; try{{sessionStorage.setItem('ma_pw','ok');}}catch(e){{}} }} else{{ document.getElementById('lockMsg').innerText='密碼錯誤'; }} }}
  document.getElementById('enterBtn').addEventListener('click', unlock);
  document.getElementById('pw').addEventListener('keydown', e=>{{ if(e.key==='Enter') unlock(); }});
  try{{ if(sessionStorage.getItem('ma_pw')==='ok') document.getElementById('lock').style.display='none'; }}catch(e){{}}
}})();

let focusDots = JSON.parse(localStorage.getItem('focusDotsV20')||localStorage.getItem('focusDotsV19')||'{{}}');
let focusMa = JSON.parse(localStorage.getItem('focusMaV20')||localStorage.getItem('focusMaV19')||'{{}}');

document.addEventListener('click', function(e){{
  let dots = e.target.closest('.dots');
  if(dots){{ dots.classList.toggle('white'); let t=dots.getAttribute('data-ticker'); if(t){{ if(dots.classList.contains('white')) focusDots[t]=1; else delete focusDots[t]; localStorage.setItem('focusDotsV20', JSON.stringify(focusDots)); }} return; }}
  let mbox = e.target.closest('.ma-box');
  if(mbox){{ mbox.classList.toggle('white'); let t=mbox.getAttribute('data-ticker'); if(t){{ if(mbox.classList.contains('white')) focusMa[t]=1; else delete focusMa[t]; localStorage.setItem('focusMaV20', JSON.stringify(focusMa)); }} return; }}
  let star = e.target.closest('.star');
  if(star){{ let ticker=star.getAttribute('data-pin'); if(ticker) togglePin(ticker); return; }}
}});

function applyFocus(){{ document.querySelectorAll('.dots[data-ticker]').forEach(el=>{{ if(focusDots[el.getAttribute('data-ticker')]) el.classList.add('white'); }}); document.querySelectorAll('.ma-box[data-ticker]').forEach(el=>{{ if(focusMa[el.getAttribute('data-ticker')]) el.classList.add('white'); }}); }}

function saveLayout(){{ let order={{}}; ['grid','pinnedGrid','grid-hk','grid-index','grid-waiting'].forEach(id=>{{ let el=document.getElementById(id); if(!el) return; order[id]=Array.from(el.children).map(c=>c.getAttribute('data-ticker')).filter(Boolean); }}); localStorage.setItem('layoutOrderV20', JSON.stringify(order)); }}
function initSortable(){{ ['grid','pinnedGrid','grid-hk','grid-index','grid-waiting'].forEach(id=>{{ let el=document.getElementById(id); if(!el) return; if(el._sortable) el._sortable.destroy(); el._sortable = new Sortable(el, {{ group: 'shared', animation:150, ghostClass:'sortable-ghost', chosenClass:'sortable-chosen', onEnd: ()=>{{ saveLayout(); renderPins(); }} }}); }}); }}
function restoreLayout(){{ try{{ let order=JSON.parse(localStorage.getItem('layoutOrderV20')||localStorage.getItem('layoutOrderV19')||'{{}}'); Object.keys(order).forEach(gridId=>{{ let grid=document.getElementById(gridId); if(!grid) return; let map={{}}; document.querySelectorAll('.card').forEach(c=>{{ map[c.getAttribute('data-ticker').toUpperCase()]=c; }}); order[gridId].forEach(t=>{{ let card=map[t.toUpperCase()]; if(card) grid.appendChild(card); }}); }}); }}catch(e){{}} }}

let pinnedStocks = JSON.parse(localStorage.getItem('pinnedV20')||localStorage.getItem('pinnedV19')||'[]');
function togglePin(ticker){{
  ticker=ticker.toUpperCase();
  if(pinnedStocks.includes(ticker)) pinnedStocks=pinnedStocks.filter(t=>t!==ticker); else pinnedStocks.push(ticker);
  localStorage.setItem('pinnedV20', JSON.stringify(pinnedStocks));
  let card=document.querySelector(`.card[data-ticker="${{ticker}}"]`);
  if(card){{ if(pinnedStocks.includes(ticker)) document.getElementById('pinnedGrid').appendChild(card); else document.getElementById('grid').appendChild(card); }}
  renderPins(); saveLayout(); applyFocus();
}}
function renderPins(){{
  let count=document.getElementById('pinnedGrid').children.length;
  document.getElementById('pinnedTitle').classList.toggle('show', count>0);
  document.getElementById('pinCount').innerText=count;
  document.querySelectorAll('.card').forEach(card=>{{ let t=card.getAttribute('data-ticker').toUpperCase(); let s=card.querySelector('.star'); if(!s) return; s.innerText=pinnedStocks.includes(t)?'★':'☆'; s.classList.toggle('pinned', pinnedStocks.includes(t)); }});
}}

document.getElementById('search').addEventListener('input', e=>{{ let q=e.target.value.trim().toLowerCase(); document.querySelectorAll('.grid .card').forEach(card=>{{ let code=card.getAttribute('data-code')||''; let name=card.getAttribute('data-name')||''; if(!q) card.classList.remove('hide'); else card.classList.toggle('hide', !(code.includes(q)||name.includes(q))); }}); }});

let customStocks = JSON.parse(localStorage.getItem('customStocksV20')||localStorage.getItem('customStocksV19')||'[]');
function saveCustom(){{ localStorage.setItem('customStocksV20', JSON.stringify(customStocks)); document.getElementById('customCount').innerText=customStocks.length; document.getElementById('count').innerText = {len(results)} + customStocks.length; }}
function clearCustom(){{ if(!confirm('清空所有自加？')) return; customStocks=[]; saveCustom(); document.getElementById('grid-waiting').innerHTML=''; saveLayout(); }}
document.getElementById('clearBtn').addEventListener('click', clearCustom);
document.getElementById('exportBtn').addEventListener('click', ()=>{{ if(customStocks.length===0){{ alert('還沒有自加'); return; }} let txt=JSON.stringify(customStocks.map(s=>({{code:s.code, name:s.name}})), null, 2); navigator.clipboard.writeText(txt).then(()=>alert('已複製 custom.json\\n'+txt)).catch(()=>prompt('複製',txt)); }});
function normalizeTicker(s){{ s=s.trim().toUpperCase(); if(!s) return null; if(/^\\d{{3,5}}$/.test(s)) return s+'.HK'; return s; }}
function addStock(input){{
  let raw=(input||document.getElementById('addInput').value||'').trim(); if(!raw) return;
  let tok=raw.split(/[\\s,，]+/)[0]; let ticker=normalizeTicker(tok); let name=raw.replace(tok,'').trim()||tok;
  document.getElementById('addInput').value=''; document.getElementById('yahooSuggest').style.display='none';
  if(customStocks.find(s=>s.code===ticker)){{ alert(ticker+' 已加過'); return; }}
  customStocks.push({{code:ticker, name:name}}); saveCustom();
  let id='custom-'+ticker.replace(/\\./g,'-');
  document.getElementById('grid-waiting').insertAdjacentHTML('beforeend', `<div class="card 白 custom" id="${{id}}" data-code="${{ticker.toLowerCase()}}" data-name="${{name.toLowerCase()}} ${{ticker.toLowerCase()}}" data-ticker="${{ticker}}"><div class="left"><div class="top"><b>(${{
ticker
}})${{name}}</b></div><div class="mid"><span class="price">等候區</span></div></div><div class="star" data-pin="${{ticker}}">☆</div></div>`);
  saveLayout(); applyFocus();
}}
document.getElementById('addBtn').addEventListener('click', ()=>addStock());
function removeCustom(t){{ customStocks=customStocks.filter(s=>s.code!==t.toUpperCase()); localStorage.setItem('customStocksV20',JSON.stringify(customStocks)); saveCustom(); let el=document.getElementById('custom-'+t.replace(/\\./g,'-')); if(!el) el=document.querySelector(`[data-ticker="${{t}}"]`); if(el) el.remove(); saveLayout(); renderPins(); }}
document.getElementById('addInput').addEventListener('keydown', e=>{{ if(e.key==='Enter'){{ let box=document.getElementById('yahooSuggest'); if(box.style.display!=='none' && box.firstChild) box.firstChild.click(); else addStock(); }} }});

// Yahoo HK 搜索 - 走代理解決 CORS
let yTimer=null;
document.getElementById('addInput').addEventListener('input', e=>{{
  let q=e.target.value.trim(); let box=document.getElementById('yahooSuggest');
  if(!q || q.length<1){{ box.style.display='none'; return; }}
  clearTimeout(yTimer);
  yTimer=setTimeout(async ()=>{{
    // 先試 HK Yahoo trending 再試 search API
    try{{
      // 使用 allorigins 代理
      let yUrl = `https://query1.finance.yahoo.com/v1/finance/search?q=${{encodeURIComponent(q)}}&quotesCount=12&newsCount=0&lang=zh-Hant&region=HK`;
      let proxy = `https://api.allorigins.win/raw?url=${{encodeURIComponent(yUrl)}}`;
      let r = await fetch(proxy);
      if(!r.ok) throw 'proxy fail';
      let d = await r.json();
      let quotes = d.quotes||[];
      if(quotes.length===0) throw 'no quotes';
      box.innerHTML='';
      quotes.forEach(it=>{{
        let sym=it.symbol;
        let name=it.shortname||it.longname||sym;
        let exch=it.exchange||it.exchDisp||'';
        let longN = it.longname||'';
        let div=document.createElement('div'); div.className='s-item';
        div.innerHTML=`<span><b>${{sym}}</b> ${{name}} ${{longN && longN!==name ? '<small style=color:#94a3b8>'+longN+'</small>':''}}</span><span>${{exch}}</span>`;
        div.onclick=()=>{{ document.getElementById('addInput').value=sym+' '+name; box.style.display='none'; addStock(sym+' '+name); }};
        box.appendChild(div);
      }});
      box.style.display='block';
      return;
    }}catch(err){{ console.log('proxy search fail', err); }}
    try{{
      // 備用：直接試不帶代理 (有些瀏覽器可能通)
      let r2 = await fetch(`https://query1.finance.yahoo.com/v1/finance/search?q=${{encodeURIComponent(q)}}&quotesCount=10&newsCount=0`);
      let d2 = await r2.json();
      let quotes2 = d2.quotes||[];
      box.innerHTML='';
      quotes2.forEach(it=>{{
        let div=document.createElement('div'); div.className='s-item';
        div.innerHTML=`<span><b>${{it.symbol}}</b> ${{it.shortname||it.longname||''}}</span>`;
        div.onclick=()=>{{ document.getElementById('addInput').value=it.symbol; box.style.display='none'; addStock(it.symbol); }};
        box.appendChild(div);
      }});
      box.style.display= quotes2.length?'block':'none';
    }}catch(e){{ box.style.display='none'; }}
  }}, 280);
}});
document.addEventListener('click', e=>{{ if(!e.target.closest('.addRow')) document.getElementById('yahooSuggest').style.display='none'; }});

(function(){{
  saveCustom();
  customStocks.forEach(s=>{{
    let id='custom-'+s.code.replace(/\\./g,'-');
    if(document.getElementById(id)) return;
    let disp = `(${{s.code}})${{s.name}}`;
    if(disp.length>35) disp=disp.slice(0,34)+'...';
    document.getElementById('grid-waiting').insertAdjacentHTML('beforeend', `<div class="card 白 custom" id="${{id}}" data-code="${{s.code.toLowerCase()}}" data-name="${{s.name.toLowerCase()}} ${{s.code.toLowerCase()}}" data-ticker="${{s.code}}"><div class="left"><div class="top"><b>${{disp}}</b></div><div class="mid"><span class="price">等候區</span></div></div><div class="star" data-pin="${{s.code}}">☆</div></div>`);
  }});
  fetch('data.json').then(r=>r.json()).then(j=>{{
    j.results.forEach(r=>{{
      let card=document.getElementById('custom-'+r.code.replace(/\\./g,'-'));
      if(card){{
        let display=r.display||`(${{r.code}})${{r.name}}`;
        if(display.length>35) display=display.slice(0,34)+'…';
        let pctCls=r.pct>=0?'pct-up':'pct-down'; let sign=r.pct>=0?'+':'';
        let dots=`<span class="dots ${{focusDots[r.code]?'white':''}}" data-ticker="${{r.code}}"><span class="dot ${{r.pre}}"></span><span class="arrow">→</span><span class="dot ${{r.yesterday}}"></span><span class="arrow">→</span><span class="dot ${{r.today}}"></span></span>`;
        let rsi=''; if(r.rsi14!=null){{ let cls=r.rsi14>=70?'rsi-green':r.rsi14<=30?'rsi-red':''; rsi=`<span class='rsi-inline ${{cls}}'>RSI14 (${{r.rsi14.toFixed(0)}})</span>`; }}
        let ml=(l,v,c)=>{{ if(!v) return `<span class='ma-item'><span class='ma-w'>${{l}}(--)</span></span>`; let cls=v>c?'ma-red':'ma-green'; return `<span class='ma-item'><span class='ma-w'>${{l}}</span><span class='${{cls}}'>(${{v.toFixed(0)}})</span></span>`; }};
        let dRow=`<div class='ma-row'><span class='ma-w'>日k：</span>${{ml('MA20',r.d20,r.curr)}} ${{ml('MA60',r.d60,r.curr)}} ${{ml('MA240',r.d240,r.curr)}}</div>`;
        let hRow=`<div class='ma-row'><span class='ma-w'>時k：</span>${{ml('MA20',r.h20,r.curr)}} ${{ml('MA60',r.h60,r.curr)}} ${{ml('MA240',r.h240,r.curr)}}</div>`;
        card.outerHTML=`<div class="card ${{r.today}} custom" id="custom-${{r.code.replace(/\\./g,'-')}}" data-code="${{r.code.toLowerCase()}}" data-name="${{display.toLowerCase()}} ${{r.code.toLowerCase()}}" data-ticker="${{r.code}}"><div class="left"><div class="top"><b>${{display}}</b> ${{dots}}</div><div class="mid"><span class="price">$${{r.curr}}</span> <span class="pct ${{pctCls}}">${{sign}}${{r.pct.toFixed(2)}}%</span> ${{rsi}}</div><div class="ma-box ${{focusMa[r.code]?'white':''}}" data-ticker="${{r.code}}"><div class="ma-inner">${{dRow}}${{hRow}}</div></div></div><div class="star" data-pin="${{r.code}}">${{pinnedStocks.includes(r.code)?'★':'☆'}}</div></div>`;
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
print("V20 生成")
