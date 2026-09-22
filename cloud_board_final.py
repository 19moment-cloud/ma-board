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
    ("TSLA", "特斯拉"), ("SPY", "標普500"), ("QQQ", "納指QQQ"), ("LI", "理想汽車"), ("NIO", "蔚來"),
    ("BABA", "阿里巴巴"), ("FUTU", "富途"), ("NVDA", "輝達"), ("AMD", "超微"), ("INTC", "英特爾"),
    ("AAPL", "蘋果"), ("GOOGL", "谷歌-A"), ("GOOG", "谷歌-C"), ("MSFT", "微軟"), ("AMZN", "亞馬遜"),
    ("^GSPC", "標普500指數"), ("^IXIC", "納指"), ("^DJI", "道瓊"), ("^HSI", "恒生指數"), ("^N225", "日經225"), ("^FTSE", "富時100"),
]

CN_NAME_MAP = {
    "XIACY": "小米集團", "01810.HK": "小米集團-W",
    "BABA": "阿里巴巴", "09988.HK": "阿里巴巴-W",
    "NIO": "蔚來", "09866.HK": "蔚來-W",
    "LI": "理想汽車", "02015.HK": "理想汽車-W",
    "XPEV": "小鵬汽車", "09868.HK": "小鵬汽車-W",
    "BIDU": "百度", "09888.HK": "百度-W",
    "FUTU": "富途控股", "TSLA": "特斯拉", "AAPL": "蘋果", "NVDA": "英偉達",
    "MSFT": "微軟", "GOOGL": "谷歌-A", "GOOG": "谷歌-C", "AMZN": "亞馬遜",
    "MU": "美光科技", "AMD": "超微半導體", "INTC": "英特爾",
    "^GSPC": "標普500指數", "^IXIC": "納斯達克指數", "^DJI": "道瓊工業指數",
    "^HSI": "恒生指數", "^N225": "日經225", "^FTSE": "富時100",
    "SPY": "標普500ETF", "QQQ": "納指ETF", "TQQQ": "納指3倍做多", "SQQQ": "納指3倍做空",
}

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

def clean_yahoo_name(raw, code):
    if not raw: return CN_NAME_MAP.get(code, code)
    raw = str(raw).strip()
    bad_keywords = ["來自 Yahoo", "股票代號查詢", "Yahoo 財經", "xStock", "tokenized"]
    for bad in bad_keywords:
        if bad in raw:
            return CN_NAME_MAP.get(code, code)
    raw = re.sub(r'\(.*?\)', '', raw).strip()
    if len(raw) > 28: raw = raw[:28]
    if not raw: return CN_NAME_MAP.get(code, code)
    return raw

def get_yahoo_name(tk, code, fallback):
    if code in CN_NAME_MAP:
        base = CN_NAME_MAP[code]
    else:
        base = fallback
    try:
        info = {}
        try: info = tk.info if tk else {}
        except: info = {}
        long_name = info.get('longName') or info.get('displayName') or info.get('shortName') or base
        cleaned = clean_yahoo_name(long_name, code)
        if code in CN_NAME_MAP and CN_NAME_MAP[code]:
            if code.startswith('^'): return CN_NAME_MAP[code]
            if len(cleaned) > 2 and all(ord(c) < 128 for c in cleaned):
                return CN_NAME_MAP[code]
            return cleaned
        return cleaned
    except:
        return CN_NAME_MAP.get(code, fallback)

def format_display(code, name):
    """(代號)名稱，最多30位"""
    clean_name = re.sub(r'\s*\(.*?\)\s*', '', str(name)).strip()
    if not clean_name: clean_name = code
    if "來自 Yahoo" in clean_name or "查詢" in clean_name:
        clean_name = CN_NAME_MAP.get(code, code)
    full = f"({code}){clean_name}"
    if len(full) > 30:
        remain = 30 - len(f"({code})")
        if remain <= 0:
            full = f"({code})"[:30]
        else:
            if remain > 1:
                clean_name = clean_name[:remain-1] + "…"
            else:
                clean_name = clean_name[:remain]
            full = f"({code}){clean_name}"
            if len(full) > 30: full = full[:30]
    return full

results=[]
for code,name in WATCHLIST:
    try:
        df_day, tk = get_history(code,"1y","1d",False)
        raw_name = get_yahoo_name(tk, code, name)
        display = format_display(code, raw_name)
        if df_day.empty or len(df_day)<65:
            results.append({"code":code,"name":name,"display":display,"today":"白","yesterday":"白","pre":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None})
            time.sleep(0.8); continue
        df_60m, _ = get_history(code,"60d","60m",True)
        if df_60m.empty:
            results.append({"code":code,"name":name,"display":display,"today":"白","yesterday":"白","pre":"白","curr":float(df_day['Close'].iloc[-1]),"pct":0,"d20":calc_ma(df_day['Close'],20),"d60":calc_ma(df_day['Close'],60),"d240":calc_ma(df_day['Close'],240),"h20":0,"h60":0,"h240":0,"rsi14":None})
            time.sleep(0.8); continue
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
        results.append({"code":code,"name":name,"display":display,"today":today,"yesterday":yesterday,"pre":pre,"curr":round(curr,2),"pct":round(pct,2),"d20":round(d20_t,2),"d60":round(d60_t,2),"d240":round(d240_t,2),"h20":round(h20_t,2),"h60":round(h60_t,2),"h240":round(h240_t,2),"rsi14":rsi14})
        time.sleep(0.8)
    except Exception as e:
        print(f"{code} err {e}")
        results.append({"code":code,"name":name,"display":format_display(code, CN_NAME_MAP.get(code, name)),"today":"白","yesterday":"白","pre":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None})

order={"白":-1,"灰":0,"紅":1,"藍":2,"綠":3,"橙":4}
results.sort(key=lambda x: order.get(x["today"],0), reverse=True)
hk_now = datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M:%S")
os.makedirs("docs", exist_ok=True)
with open("docs/data.json","w",encoding="utf-8") as f:
    json.dump({"update":hk_now+" 香港時間","results":results},f,ensure_ascii=False,indent=2)

# Telegram
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
    <div class="top"><b title="{display}">{display}</b> {dots}</div>
    <div class="mid">{curr_html} {pct_html} {rsi_html}</div>
    <div class="ma-box" data-ticker='{r['code']}'><div class="ma-inner">{d_row}{h_row}</div></div>
  </div>
  <div class="star" data-pin='{r['code']}'>☆</div>
</div>"""

html_template = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MA看板 私有版</title>
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
<style>
*{box-sizing:border-box} body{font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial;background:#0a0e14;color:#e6e6e6;padding:14px;margin:0}
#lock{position:fixed;inset:0;background:#0a0e14;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:9999}
#lock input{padding:14px 18px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:18px;text-align:center;margin:14px;width:240px}
#lock button{padding:12px 28px;border-radius:12px;border:none;background:#f59e0b;color:#000;font-weight:800;font-size:16px;cursor:pointer}
.header{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:10px 0} h1{font-size:18px;margin:0} .search{flex:1;min-width:180px;max-width:300px;position:relative} 
.search input{width:100%;padding:10px 14px 10px 36px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:12px;outline:none} .search input:focus{border-color:#f59e0b}
.search .icon{position:absolute;left:12px;top:50%;transform:translateY(-50%);font-size:14px;pointer-events:none}
.sub{color:#94a3b8;font-size:11px;margin-bottom:12px}
.addRow{display:flex;gap:8px;align-items:center;margin:0 0 12px;flex-wrap:wrap;position:relative} .addRow input{flex:1;min-width:200px;max-width:400px;padding:10px 14px;border-radius:12px;border:1px solid #334155;background:#1e293b;color:#fff;font-size:12px;outline:none} .addRow input:focus{border-color:#f59e0b} .addbtn{padding:10px 16px;border-radius:12px;border:none;background:#f59e0b;color:#000;font-weight:800;cursor:pointer;white-space:nowrap}
#yahooSuggest{position:absolute;top:44px;left:0;width:480px;max-width:90vw;background:#fff;border:1px solid #ddd;border-radius:8px;z-index:200;display:none;max-height:420px;overflow-y:auto;box-shadow:0 8px 24px rgba(0,0,0,0.3)}
#yahooSuggest .s-head{padding:8px 14px;font-size:12px;color:#666;border-bottom:1px solid #eee;background:#f8f9fa;display:flex;justify-content:space-between}
#yahooSuggest .s-item{padding:10px 14px;cursor:pointer;border-bottom:1px solid #eee;font-size:13px;display:flex;flex-direction:column;gap:2px} #yahooSuggest .s-item:hover{background:#f0f6ff}
#yahooSuggest .s-item .s-row1{display:flex;justify-content:space-between;align-items:center}
#yahooSuggest .s-item .s-code{color:#1a73e8;font-weight:700;font-size:13px} #yahooSuggest .s-item .s-type{color:#666;font-size:11px;background:#f1f3f4;padding:2px 6px;border-radius:4px}
#yahooSuggest .s-item .s-name{color:#333;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#yahooSuggest .loading{padding:12px 14px;color:#888;font-size:12px;text-align:center}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px;align-items:start;min-height:20px}
.section{margin-top:18px} .section-title{font-size:13px;color:#94a3b8;margin:0 0 8px;padding-left:4px;border-left:3px solid #f59e0b}
.pinned-section{margin-bottom:14px} .pinned-title{font-size:13px;color:#fde68a;margin:0 0 8px;display:none} .pinned-title.show{display:block}
.card{border-radius:14px;padding:11px 13px;display:flex;justify-content:space-between;align-items:flex-start;gap:10px;min-height:115px;overflow:hidden;position:relative;cursor:grab} .card.hide{display:none} .sortable-ghost{opacity:0.3} .sortable-chosen{border:2px solid #f59e0b !important}
.橙{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000} .綠{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000} .灰{background:#1e293b;color:#cbd5e1;border:1px solid #2a3441} .藍{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff} .紅{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff} .白{background:#fff;color:#000;border:2px dashed #94a3b8}
.star{font-size:20px;cursor:pointer;user-select:none;line-height:1;padding:2px 4px;border-radius:6px;flex-shrink:0} .star.pinned{color:#f59e0b} 
.left{flex:1;min-width:0} .top{font-size:12px;display:flex;align-items:center;gap:6px;flex-wrap:wrap} .top b{max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block} .mid{margin-top:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.price{color:#facc15;font-weight:900;font-size:15px;background:rgba(0,0,0,0.32);padding:2px 8px;border-radius:6px} .白 .price{background:#000;color:#fff}
.pct{font-size:11px;font-weight:800;padding:3px 8px;border-radius:6px;background:rgba(0,0,0,0.45);color:#fff} .pct-up{color:#4ade80} .pct-down{color:#f87171}
.dots{display:inline-flex;align-items:center;background:#000;padding:3px 8px;border-radius:12px;gap:3px;cursor:pointer;user-select:none;border:1px solid #111} .dots.white{background:#fff !important;border-color:#ddd} .dots .arrow{font-size:10px;color:#fff} .dots.white .arrow{color:#000} .dot{width:9px;height:9px;border-radius:50%;display:inline-block} .dot.橙{background:#ff8a00} .dot.綠{background:#00c853} .dot.藍{background:#2962ff} .dot.紅{background:#d50000} .dot.灰{background:#94a3b8} .dot.白{background:#fff;border:1px solid #000}
.rsi-inline{font-size:11px;font-weight:800;padding:3px 7px;border-radius:6px;background:rgba(0,0,0,0.35);margin-left:2px} .rsi-inline.rsi-green{color:#4ade80;border:1px solid #22c55e} .rsi-inline.rsi-red{color:#f87171;border:1px solid #ef4444}
.ma-box{margin-top:6px;background:#000;border-radius:8px;padding:7px 9px;border:1px solid #111;cursor:pointer} .ma-box.white{background:#fff;border-color:#ddd} .ma-row{font-size:11px;line-height:1.7;display:flex;flex-wrap:wrap;gap:6px} .ma-w{color:#fff;font-weight:600} .ma-box.white .ma-w{color:#000 !important} .ma-item{white-space:nowrap} .ma-green{color:#4ade80;font-weight:900} .ma-red{color:#f87171;font-weight:900} .ma-same{color:#fff} .ma-box.white .ma-same{color:#000}
.ver{background:#78350f;color:#fde68a;border:1px solid #92400e;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:800}
</style></head><body>

<div id="lock">
<h2>🔒 私有看板</h2>
<div style="color:#94a3b8;font-size:13px">請輸入密碼</div>
<input id="pw" type="password" placeholder="請輸入密碼" autocomplete="off"/>
<button id="enterBtn" type="button">進入</button>
<div id="lockMsg" style="color:#f87171;font-size:13px;margin-top:12px;min-height:20px;font-weight:700"></div>
</div>

<div class="header">
<h1><a href="https://hk.finance.yahoo.com/markets" target="_blank" style="text-decoration:none" title="Yahoo HK">🚀</a> MA(20/60/240) 私有版 <span class="ver">V22</span></h1>
<div class="search"><span class="icon">🔍</span><input id="search" type="text" placeholder="搜索代號/名稱" /></div>
</div>

<div class="addRow"><input id="addInput" type="text" placeholder="加股：輸入自動出現選單" autocomplete="off"/><div id="yahooSuggest"></div><button class="addbtn" id="addBtn">+ 加股</button><button class="addbtn" id="clearBtn" style="background:#1e293b;color:#fff;border:1px solid #334155">清空自加</button></div>

<div class="sub">更新: __UPDATE_TIME__ 香港時間 | 共<span id="count">__COUNT__</span>隻 自加<span id="customCount">0</span>隻 置頂<span id="pinCount">0</span>隻 |</div>

<div class="pinned-section"><div id="pinnedTitle" class="pinned-title">⭐ 置頂觀察 (可拖動排序)</div><div id="pinnedGrid" class="grid"></div></div>

<div class="grid" id="grid">__CARDS__</div>

<div class="section"><div class="section-title">.HK</div><div class="grid" id="grid-hk"></div></div>
<div class="section"><div class="section-title">指數</div><div class="grid" id="grid-index"></div></div>
<div class="section"><div class="section-title">等候 (自加待建 custom.json)</div><div class="grid" id="grid-waiting"></div></div>

<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px;margin:14px 0;font-size:11px;line-height:1.8">
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
// ===== 鎖屏 =====
(function(){
  var REAL_PW = "88666666";
  function doUnlock(){
    var input = document.getElementById('pw');
    var msg = document.getElementById('lockMsg');
    var v = (input.value||'').trim();
    if(!v){ msg.textContent="請輸入密碼"; return; }
    if(v === REAL_PW){
      document.getElementById('lock').style.display='none';
      msg.textContent="";
      try{ sessionStorage.setItem('ma_pw','ok'); }catch(e){}
    }else{
      msg.textContent="❌ 密碼錯誤";
      input.value=""; input.focus();
      input.style.borderColor="#ef4444";
      setTimeout(function(){ input.style.borderColor="#334155"; }, 2000);
    }
  }
  document.addEventListener('DOMContentLoaded', function(){
    var btn = document.getElementById('enterBtn');
    var pw = document.getElementById('pw');
    if(btn){ btn.addEventListener('click', doUnlock); btn.onclick = doUnlock; }
    if(pw){ pw.addEventListener('keydown', function(e){ if(e.key==='Enter'){ e.preventDefault(); doUnlock(); } }); pw.focus(); }
    try{ if(sessionStorage.getItem('ma_pw')==='ok'){ document.getElementById('lock').style.display='none'; } }catch(e){}
  });
})();

// ===== 永久保存的 key - V22後不再變 =====
var LAYOUT_KEY = "ma_board_layout_permanent";
var PIN_KEY = "ma_board_pins_permanent";
var FOCUS_DOTS_KEY = "ma_board_focus_dots";
var FOCUS_MA_KEY = "ma_board_focus_ma";
var CUSTOM_KEY = "ma_board_custom_permanent";

function getLayoutKey(){
  // 遷移舊版本
  var oldKeys = ["layoutOrderV21","layoutOrderV20","layoutOrderV19","layoutOrder"];
  var oldData = null;
  for(var i=0;i<oldKeys.length;i++){
    try{
      var d = localStorage.getItem(oldKeys[i]);
      if(d){ oldData = d; break; }
    }catch(e){}
  }
  if(oldData && !localStorage.getItem(LAYOUT_KEY)){
    localStorage.setItem(LAYOUT_KEY, oldData);
  }
  return LAYOUT_KEY;
}

var focusDots = JSON.parse(localStorage.getItem(FOCUS_DOTS_KEY)||'{}');
var focusMa = JSON.parse(localStorage.getItem(FOCUS_MA_KEY)||'{}');

document.addEventListener('click', function(e){
  var dots = e.target.closest('.dots');
  if(dots){ dots.classList.toggle('white'); var t=dots.getAttribute('data-ticker'); if(t){ if(dots.classList.contains('white')) focusDots[t]=1; else delete focusDots[t]; localStorage.setItem(FOCUS_DOTS_KEY, JSON.stringify(focusDots)); } return; }
  var mbox = e.target.closest('.ma-box');
  if(mbox){ mbox.classList.toggle('white'); var t=mbox.getAttribute('data-ticker'); if(t){ if(mbox.classList.contains('white')) focusMa[t]=1; else delete focusMa[t]; localStorage.setItem(FOCUS_MA_KEY, JSON.stringify(focusMa)); } return; }
  var star = e.target.closest('.star');
  if(star){ var ticker=star.getAttribute('data-pin'); if(ticker) togglePin(ticker); return; }
});

function applyFocus(){ document.querySelectorAll('.dots[data-ticker]').forEach(function(el){ if(focusDots[el.getAttribute('data-ticker')]) el.classList.add('white'); }); document.querySelectorAll('.ma-box[data-ticker]').forEach(function(el){ if(focusMa[el.getAttribute('data-ticker')]) el.classList.add('white'); }); }

function saveLayout(){
  var order={};
  ['grid','pinnedGrid','grid-hk','grid-index','grid-waiting'].forEach(function(id){
    var el=document.getElementById(id);
    if(!el) return;
    order[id]=Array.from(el.children).map(function(c){return c.getAttribute('data-ticker')}).filter(Boolean);
  });
  localStorage.setItem(getLayoutKey(), JSON.stringify(order));
  console.log("已保存佈局", order);
}
function initSortable(){
  ['grid','pinnedGrid','grid-hk','grid-index','grid-waiting'].forEach(function(id){
    var el=document.getElementById(id);
    if(!el) return;
    if(el._sortable) el._sortable.destroy();
    el._sortable = new Sortable(el, { group: 'shared', animation:150, ghostClass:'sortable-ghost', chosenClass:'sortable-chosen', onEnd: function(){ saveLayout(); renderPins(); }});
  });
}
function restoreLayout(){
  try{
    var orderStr = localStorage.getItem(getLayoutKey());
    if(!orderStr){
      // 嘗試遷移舊版
      var oldKeys = ["layoutOrderV21","layoutOrderV20","layoutOrderV19","layoutOrder"];
      for(var i=0;i<oldKeys.length;i++){
        var d = localStorage.getItem(oldKeys[i]);
        if(d){ orderStr = d; localStorage.setItem(getLayoutKey(), d); console.log("遷移舊佈局", oldKeys[i]); break; }
      }
    }
    if(!orderStr) return;
    var order=JSON.parse(orderStr);
    console.log("恢復佈局", order);
    Object.keys(order).forEach(function(gridId){
      var grid=document.getElementById(gridId);
      if(!grid) return;
      var map={};
      document.querySelectorAll('.card').forEach(function(c){ map[c.getAttribute('data-ticker').toUpperCase()]=c; });
      order[gridId].forEach(function(t){
        var card=map[t.toUpperCase()];
        if(card) grid.appendChild(card);
      });
    });
  }catch(e){ console.log("恢復佈局失敗", e); }
}

function getPinKey(){
  var oldPinKeys = ["pinnedV21","pinnedV20","pinnedV19","pinned"];
  for(var i=0;i<oldPinKeys.length;i++){
    var d = localStorage.getItem(oldPinKeys[i]);
    if(d && !localStorage.getItem(PIN_KEY)){
      localStorage.setItem(PIN_KEY, d);
      console.log("遷移置頂", oldPinKeys[i]);
      break;
    }
  }
  return PIN_KEY;
}
var pinnedStocks = JSON.parse(localStorage.getItem(getPinKey())||'[]');
function togglePin(ticker){
  ticker=ticker.toUpperCase();
  if(pinnedStocks.includes(ticker)) pinnedStocks=pinnedStocks.filter(function(t){return t!==ticker}); else pinnedStocks.push(ticker);
  localStorage.setItem(getPinKey(), JSON.stringify(pinnedStocks));
  var card=document.querySelector('.card[data-ticker="'+ticker+'"]');
  if(card){ if(pinnedStocks.includes(ticker)) document.getElementById('pinnedGrid').appendChild(card); else document.getElementById('grid').appendChild(card); }
  renderPins(); saveLayout(); applyFocus();
}
function renderPins(){
  var count=document.getElementById('pinnedGrid').children.length;
  document.getElementById('pinnedTitle').classList.toggle('show', count>0);
  document.getElementById('pinCount').innerText=count;
  document.querySelectorAll('.card').forEach(function(card){ var t=card.getAttribute('data-ticker').toUpperCase(); var s=card.querySelector('.star'); if(!s) return; s.innerText=pinnedStocks.includes(t)?'★':'☆'; s.classList.toggle('pinned', pinnedStocks.includes(t)); });
}

document.getElementById('search').addEventListener('input', function(e){
  var q=e.target.value.trim().toLowerCase();
  document.querySelectorAll('.grid .card').forEach(function(card){
    var code=card.getAttribute('data-code')||'';
    var name=card.getAttribute('data-name')||'';
    if(!q) card.classList.remove('hide');
    else card.classList.toggle('hide', !(code.includes(q)||name.includes(q)));
  });
});

function getCustomKey(){
  var oldKeys = ["customStocksV21","customStocksV20","customStocksV19"];
  for(var i=0;i<oldKeys.length;i++){
    var d = localStorage.getItem(oldKeys[i]);
    if(d && !localStorage.getItem(CUSTOM_KEY)){
      localStorage.setItem(CUSTOM_KEY, d);
      console.log("遷移自加", oldKeys[i]);
      break;
    }
  }
  return CUSTOM_KEY;
}
var customStocks = JSON.parse(localStorage.getItem(getCustomKey())||'[]');
function saveCustom(){ localStorage.setItem(getCustomKey(), JSON.stringify(customStocks)); document.getElementById('customCount').innerText=customStocks.length; }
function normalizeTicker(s){ s=s.trim().toUpperCase(); if(!s) return null; if(/^\\d{3,5}$/.test(s)) return s+'.HK'; return s; }
function addStock(input){
  var raw=(input||document.getElementById('addInput').value||'').trim(); if(!raw) return;
  var tok=raw.split(/[\\s,，]+/)[0]; var ticker=normalizeTicker(tok); var name=raw.replace(tok,'').trim()||tok;
  document.getElementById('addInput').value=''; document.getElementById('yahooSuggest').style.display='none';
  if(customStocks.find(function(s){return s.code===ticker})){ alert(ticker+' 已加過'); return; }
  customStocks.push({code:ticker, name:name}); saveCustom();
  var disp='('+ticker+')'+name; if(disp.length>30) disp=disp.slice(0,29)+'…';
  document.getElementById('grid-waiting').insertAdjacentHTML('beforeend', '<div class="card 白 custom" data-code="'+ticker.toLowerCase()+'" data-name="'+name.toLowerCase()+'" data-ticker="'+ticker+'"><div class="left"><div class="top"><b>'+disp+'</b></div><div class="mid"><span class="price">等候區</span></div></div><div class="star" data-pin="'+ticker+'">☆</div></div>');
  saveLayout();
}
document.getElementById('addBtn').addEventListener('click', function(){ addStock(); });
document.getElementById('clearBtn').addEventListener('click', function(){ if(!confirm('清空所有自加？')) return; customStocks=[]; saveCustom(); document.getElementById('grid-waiting').innerHTML=''; saveLayout(); });
document.getElementById('exportBtn').addEventListener('click', function(){ if(customStocks.length===0){ alert('還沒有自加'); return; } var txt=JSON.stringify(customStocks.map(function(s){return {code:s.code, name:s.name}}), null, 2); navigator.clipboard.writeText(txt).then(function(){alert('已複製 custom.json\\n'+txt)}).catch(function(){prompt('複製',txt)}); });
document.getElementById('addInput').addEventListener('keydown', function(e){ if(e.key==='Enter'){ var box=document.getElementById('yahooSuggest'); if(box.style.display!=='none' && box.firstChild && !box.firstChild.classList.contains('loading') && !box.firstChild.classList.contains('s-head')) box.firstChild.nextSibling ? box.firstChild.nextSibling.click() : box.children[1].click(); else addStock(); } });

// ===== Yahoo 搜索優化版 - 無延遲、緩存、並行 =====
var yTimer=null;
var yahooCache={};
var lastQuery="";
var yahooSuggest=document.getElementById('yahooSuggest');

document.getElementById('addInput').addEventListener('input', function(e){
  var q=e.target.value.trim();
  if(!q || q.length<1){ yahooSuggest.style.display='none'; return; }
  clearTimeout(yTimer);
  // 立即顯示加載中
  if(q.length>=1){
    yahooSuggest.innerHTML='<div class="loading">搜索 '+q+'...</div>';
    yahooSuggest.style.display='block';
  }
  yTimer=setTimeout(function(){
    if(q===lastQuery && yahooCache[q]){
      renderYahooResults(yahooCache[q], q);
      return;
    }
    lastQuery=q;
    if(yahooCache[q]){
      renderYahooResults(yahooCache[q], q);
      return;
    }
    // 並行請求多個代理，誰先回用誰
    var yUrl='https://query1.finance.yahoo.com/v1/finance/search?q='+encodeURIComponent(q)+'&quotesCount=12&newsCount=0&lang=zh-Hant&region=HK';
    var proxies=[
      'https://api.allorigins.win/raw?url='+encodeURIComponent(yUrl),
      'https://corsproxy.io/?'+encodeURIComponent(yUrl)
    ];
    var done=false;
    var tryFetch = function(url, idx){
      fetch(url, {cache:'no-store'}).then(function(r){
        if(!r.ok) throw 'fail';
        return r.json();
      }).then(function(data){
        if(done) return;
        if(!data || !data.quotes || data.quotes.length===0) return;
        done=true;
        yahooCache[q]=data.quotes;
        renderYahooResults(data.quotes, q);
      }).catch(function(){});
    };
    proxies.forEach(function(p, i){ tryFetch(p, i); });
    // 1秒後如果都沒回，隱藏
    setTimeout(function(){ if(!done){ yahooSuggest.style.display='none'; } }, 1500);
  }, 120); // 120ms 延遲，比之前300ms快很多
});

function renderYahooResults(quotes, q){
  if(!quotes || quotes.length===0){ yahooSuggest.style.display='none'; return; }
  yahooSuggest.innerHTML='<div class="s-head"><span>股票代號</span><span>Yahoo 財經</span></div>';
  quotes.forEach(function(it){
    var sym=it.symbol||'';
    var name=it.shortname||it.longname||sym;
    var longDesc=it.longname||'';
    if(longDesc===name) longDesc='';
    if(name.indexOf('來自 Yahoo')>=0) name=sym;
    if(longDesc.indexOf('來自 Yahoo')>=0) longDesc='';
    var typeLabel=it.quoteType==='ETF'?'ETF':(it.quoteType==='EQUITY'?'股票':(it.exchange||''));
    var div=document.createElement('div'); div.className='s-item';
    div.innerHTML='<div class="s-row1"><span class="s-code">'+sym+'</span><span class="s-type">'+typeLabel+'</span></div><div class="s-name">'+name+(longDesc?' - '+longDesc:'')+'</div>';
    div.onclick=function(){
      document.getElementById('addInput').value=sym+' '+name;
      yahooSuggest.style.display='none';
      addStock(sym+' '+name);
    };
    yahooSuggest.appendChild(div);
  });
  yahooSuggest.style.display='block';
}

document.addEventListener('click', function(e){ if(!e.target.closest('.addRow')) yahooSuggest.style.display='none'; });

(function(){
  saveCustom();
  var waiting=document.getElementById('grid-waiting');
  customStocks.forEach(function(s){
    var id='custom-'+s.code.replace(/\\./g,'-');
    if(document.getElementById(id)) return;
    var exists=false;
    document.querySelectorAll('#grid .card').forEach(function(c){ if(c.getAttribute('data-ticker')===s.code) exists=true; });
    if(exists) return;
    var disp='('+s.code+')'+s.name; if(disp.length>30) disp=disp.slice(0,29)+'…';
    waiting.insertAdjacentHTML('beforeend', '<div class="card 白 custom" id="'+id+'" data-code="'+s.code.toLowerCase()+'" data-name="'+s.name.toLowerCase()+'" data-ticker="'+s.code+'"><div class="left"><div class="top"><b>'+disp+'</b></div><div class="mid"><span class="price">等候區</span></div></div><div class="star" data-pin="'+s.code+'">☆</div></div>');
  });
  restoreLayout(); initSortable(); renderPins(); applyFocus();
})();
</script>
</body></html>
"""

html_final = html_template.replace("__UPDATE_TIME__", hk_now).replace("__COUNT__", str(len(results))).replace("__CARDS__", cards)

with open("docs/index.html","w",encoding="utf-8") as f:
    f.write(html_final)

print(f"V22 生成完成 共{len(results)}隻，30位限制，永久佈局key")
