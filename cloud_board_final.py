import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import json, os, time, requests, re, math

HK_TZ = timezone(timedelta(hours=8))
NY_TZ = timezone(timedelta(hours=-4))  # EDT, 美股交易日判斷用

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
    "XIACY": "小米集團", "01810.HK": "小米集團-W", "BABA": "阿里巴巴", "09988.HK": "阿里巴巴-W",
    "NIO": "蔚來", "09866.HK": "蔚來-W", "LI": "理想汽車", "02015.HK": "理想汽車-W",
    "XPEV": "小鵬汽車", "09868.HK": "小鵬汽車-W", "BIDU": "百度", "09888.HK": "百度-W",
    "FUTU": "富途控股", "TSLA": "特斯拉", "AAPL": "蘋果", "NVDA": "英偉達",
    "MSFT": "微軟", "GOOGL": "谷歌-A", "GOOG": "谷歌-C", "AMZN": "亞馬遜",
    "MU": "美光科技", "AMD": "超微半導體", "INTC": "英特爾",
    "^GSPC": "標普500指數", "^IXIC": "納斯達克指數", "^DJI": "道瓊工業平均指數",
    "^HSI": "恒生指數", "^N225": "日經225", "^FTSE": "富時100",
    "SPY": "標普500ETF", "QQQ": "納指ETF", "TQQQ": "納指3倍做多", "SQQQ": "納指3倍做空",
    "BTC-USD": "比特幣", "ETH-USD": "以太坊",
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

def cci(df, period=14):
    try:
        # V35 確保High Low Close都存在，否則用Close代替
        high = df['High'] if 'High' in df.columns else df['Close']
        low = df['Low'] if 'Low' in df.columns else df['Close']
        close = df['Close']
        tp = (high + low + close) / 3.0
        ma = tp.rolling(window=period).mean()
        md = tp.rolling(window=period).apply(lambda x: abs(x - x.mean()).mean(), raw=True)
        cci_val = (tp - ma) / (0.015 * md.replace(0, 1e-10))
        return cci_val
    except Exception as e:
        # fallback 全50
        return pd.Series([0]*len(df), index=df.index)

def skdj(df, n=9, m=6):
    try:
        low_list = df['Low'].rolling(window=n, min_periods=n).min()
        high_list = df['High'].rolling(window=n, min_periods=n).max()
        rsv = (df['Close'] - low_list) / (high_list - low_list).replace(0, 1e-10) * 100
        rsv = rsv.fillna(50)
        k = rsv.rolling(window=m, min_periods=m).mean()
        d = k.rolling(window=m, min_periods=m).mean()
        k = k.fillna(50)
        d = d.fillna(50)
        return k, d
    except:
        return None, None

def calc_ma_realtime(close_series, p, curr_price):
    try:
        if len(close_series) < p-1: return 0
        s = close_series.copy()
        if curr_price>0:
            s.iloc[-1] = curr_price
        v = float(s.rolling(p).mean().iloc[-1])
        if math.isnan(v): return 0
        return v
    except:
        return 0

def calc_ma(s, p):
    try:
        if len(s) < p: return 0
        v = float(s.rolling(p).mean().iloc[-1])
        if math.isnan(v): return 0
        return v
    except:
        return 0

def safe_num(v):
    try:
        if v is None: return 0
        if isinstance(v,float) and math.isnan(v): return 0
        return float(v)
    except:
        return 0

def calc_color(d_close, d20, d60, d240, h_close, h20, h60, h240):
    d_close=safe_num(d_close); d20=safe_num(d20); d60=safe_num(d60); d240=safe_num(d240)
    h_close=safe_num(h_close); h20=safe_num(h20); h60=safe_num(h60); h240=safe_num(h240)
    if d60==0: return "白"
    if h20==0: h20=d20
    if h60==0: h60=d60
    if h240==0: h240=d240
    if h_close==0: h_close=d_close
    if d_close > d60 and h_close > h60 and h_close > h240 and h240>0: return "橙"
    if d_close > d20 and h_close > h60: return "綠"
    if d_close < d20 and h_close < h20: return "藍"
    if d_close < d60 and h_close < h60: return "紅"
    return "灰"

def clean_yahoo_name(raw, code):
    if not raw: return CN_NAME_MAP.get(code, code)
    raw = str(raw).strip()
    for bad in ["來自 Yahoo", "股票代號查詢", "Yahoo 財經", "xStock", "tokenized"]:
        if bad in raw: return CN_NAME_MAP.get(code, code)
    raw = re.sub(r'\(.*?\)', '', raw).strip()
    if len(raw) > 28: raw = raw[:28]
    if not raw: return CN_NAME_MAP.get(code, code)
    return raw

def get_yahoo_name_from_info(info, code, fallback):
    if code in CN_NAME_MAP: base = CN_NAME_MAP[code]
    else: base = fallback
    try:
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
    clean_name = re.sub(r'\s*\(.*?\)\s*', '', str(name)).strip()
    if not clean_name: clean_name = code
    if "來自 Yahoo" in clean_name or "查詢" in clean_name:
        clean_name = CN_NAME_MAP.get(code, code)
    full = f"({code}){clean_name}"
    if len(full) > 30:
        remain = 30 - len(f"({code})")
        if remain <= 0: full = f"({code})"[:30]
        else:
            if remain > 1: clean_name = clean_name[:remain-1] + "..."
            else: clean_name = clean_name[:remain]
            full = f"({code}){clean_name}"
            if len(full) > 30: full = full[:30]
    return full

all_tickers = [c for c,_ in WATCHLIST]
print(f"批量下載 {len(all_tickers)} 隻 日K...")
try:
    daily_batch = yf.download(all_tickers, period="1y", interval="1d", group_by='ticker', auto_adjust=True, threads=True, progress=False)
    print("日K批量完成")
except Exception as e:
    print(f"日K批量失敗 {e}")
    daily_batch = pd.DataFrame()

print("批量下載 60m 含盤前後...")
try:
    hourly_batch = yf.download(all_tickers, period="60d", interval="60m", group_by='ticker', auto_adjust=True, threads=True, progress=False, prepost=True)
    print("時K批量完成")
except Exception as e:
    print(f"時K批量失敗 {e}")
    hourly_batch = pd.DataFrame()

def extract_ticker_df(batch_df, ticker):
    try:
        if batch_df.empty:
            return pd.DataFrame()
        if isinstance(batch_df.columns, pd.MultiIndex):
            if ticker in batch_df.columns.get_level_values(0):
                df = batch_df[ticker].copy()
                df = df.dropna(how='all')
                return df
            else:
                return pd.DataFrame()
        else:
            return batch_df.copy()
    except:
        return pd.DataFrame()

results=[]
for code,name in WATCHLIST:
    try:
        df_day = extract_ticker_df(daily_batch, code) if not daily_batch.empty else pd.DataFrame()
        if df_day.empty or len(df_day)<50:
            print(f"{code} 日K批量空，回退單隻")
            try:
                tk = yf.Ticker(code)
                df_day = tk.history(period="1y", interval="1d", auto_adjust=True)
            except:
                df_day = pd.DataFrame()
            time.sleep(0.8)
        
        display = format_display(code, CN_NAME_MAP.get(code, name))
        try:
            tk_info = yf.Ticker(code).info
            raw_name = get_yahoo_name_from_info(tk_info, code, name)
            display = format_display(code, raw_name)
        except:
            pass

        if df_day.empty or len(df_day)<50:
            print(f"{code} 仍無日K -> 白")
            results.append({"code":code,"name":name,"display":display,"today":"白","yesterday":"白","pre":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None,"cci14":None,"skdj_k":[],"skdj_d":[]})
            continue
        
        df_60m_all = extract_ticker_df(hourly_batch, code) if not hourly_batch.empty else pd.DataFrame()
        if df_60m_all.empty:
            try:
                tk = yf.Ticker(code)
                df_60m_all = tk.history(period="60d", interval="60m", prepost=True, auto_adjust=True)
            except:
                df_60m_all = pd.DataFrame()
            time.sleep(0.8)
        
        # V58 關鍵：時K MA包含盤前盤後 prepost=True，不再between_time過濾，盤後停在20:00最後一根去算MA20/60/240
        df_60m_reg = df_60m_all if not df_60m_all.empty else df_day
        
# V58 curr強制實時：盤前盤中盤後都會跳，修LI 11.7 vs 11.71
        curr = None
        today_high_rt = None
        today_low_rt = None
        try:
            tk_tmp = yf.Ticker(code)
            inf = {}
            try:
                inf = tk_tmp.info
            except:
                inf = {}
            if inf:
                if inf.get('regularMarketDayHigh'):
                    today_high_rt = float(inf['regularMarketDayHigh'])
                if inf.get('regularMarketDayLow'):
                    today_low_rt = float(inf['regularMarketDayLow'])
                if inf.get('postMarketPrice') and float(inf.get('postMarketPrice',0))>0:
                    curr = float(inf['postMarketPrice'])
                if curr is None and inf.get('preMarketPrice') and float(inf.get('preMarketPrice',0))>0:
                    curr = float(inf['preMarketPrice'])
                if curr is None:
                    for k in ['currentPrice','regularMarketPrice']:
                        if inf.get(k) and float(inf.get(k,0))>0:
                            curr = float(inf[k]); break
            if curr is None:
                fi = getattr(tk_tmp, 'fast_info', None)
                if fi and getattr(fi, 'last_price', None):
                    curr = float(fi.last_price)
        except:
            pass
        if curr is None:
            curr = float(df_60m_all['Close'].iloc[-1]) if not df_60m_all.empty else float(df_day['Close'].iloc[-1])
        # V58 prev_close優先用官方previousClose解決LI單隻不對
        prev_close = None
        try:
            if inf and inf.get('regularMarketPreviousClose') and float(inf.get('regularMarketPreviousClose',0))>0:
                prev_close = float(inf['regularMarketPreviousClose'])
        except:
            pass
        if prev_close is None:
            try:
                ny_today = datetime.now(NY_TZ).date()
                last_60m_date = df_60m_all.index[-1].date() if not df_60m_all.empty else df_day.index[-1].date()
                last_day_date = df_day.index[-1].date()
                if last_day_date == ny_today or last_day_date == last_60m_date:
                    prev_close = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else curr
                else:
                    prev_close = float(df_day['Close'].iloc[-1]) if len(df_day)>=1 else curr
            except:
                prev_close = float(df_day['Close'].iloc[-2]) if len(df_day)>=2 else curr
        pct = (curr/prev_close-1)*100 if prev_close else 0
        
        # 日K MA 實時（用curr替換最後收盤）
        d_close_t = curr
        d20_t = calc_ma_realtime(df_day['Close'],20,curr)
        d60_t = calc_ma_realtime(df_day['Close'],60,curr)
        d240_t = calc_ma_realtime(df_day['Close'],240,curr)
        
        # 時K MA 實時且包含盤前盤後
        h20_t = calc_ma_realtime(df_60m_reg['Close'],20,curr)
        h60_t = calc_ma_realtime(df_60m_reg['Close'],60,curr)
        h240_t = calc_ma_realtime(df_60m_reg['Close'],240,curr)
        h_close_t = curr
        
        today = calc_color(d_close_t, d20_t, d60_t, d240_t, h_close_t, h20_t, h60_t, h240_t)
        
        df_day_y = df_day.iloc[:-1] if len(df_day)>1 else df_day
        d_close_y = float(df_day_y['Close'].iloc[-1])
        d20_y = calc_ma(df_day_y['Close'],20); d60_y = calc_ma(df_day_y['Close'],60); d240_y = calc_ma(df_day_y['Close'],240)
        try:
            today_date = df_day.index[-1].date()
            df_60m_y = df_60m_reg[df_60m_reg.index.date < today_date] if not df_60m_reg.empty else pd.DataFrame()
            if len(df_60m_y)<15: df_60m_y = df_60m_reg.iloc[:-7] if len(df_60m_reg)>7 else df_60m_reg
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
            df_60m_pre = df_60m_reg[df_60m_reg.index.date < y_date] if not df_60m_reg.empty else pd.DataFrame()
            if len(df_60m_pre)<15: df_60m_pre = df_60m_reg.iloc[:-14] if len(df_60m_reg)>14 else df_60m_reg
            h20_pre = calc_ma(df_60m_pre['Close'],20); h60_pre = calc_ma(df_60m_pre['Close'],60); h240_pre = calc_ma(df_60m_pre['Close'],240)
            h_close_pre = float(df_60m_pre['Close'].iloc[-1]) if len(df_60m_pre)>0 else d_close_pre
            pre = calc_color(d_close_pre, d20_pre, d60_pre, d240_pre, h_close_pre, h20_pre, h60_pre, h240_pre)
        except:
            pre = yesterday
        
        # V35 CCI 修復：確保一定有值
        try:
            close_rt = df_day['Close'].copy()
            close_rt.iloc[-1]=curr
            rsi14 = float(rsi(close_rt,14).iloc[-1]) if len(close_rt)>=15 else None
            if rsi14 is not None and math.isnan(rsi14): rsi14=None
        except:
            rsi14=None
        try:
            df_rt = df_day.copy()
            today_dt = df_day.index[-1].date() if len(df_day)>0 else None
            today_high = None
            today_low = None
            try:
                if not df_60m_all.empty and today_dt is not None:
                    today_bars = df_60m_all[df_60m_all.index.date == today_dt]
                    if not today_bars.empty:
                        if 'High' in today_bars.columns:
                            today_high = float(today_bars['High'].max())
                        if 'Low' in today_bars.columns:
                            today_low = float(today_bars['Low'].min())
            except:
                pass
            last_idx = -1
            df_rt.iloc[last_idx, df_rt.columns.get_loc('Close')] = curr
            if 'High' in df_rt.columns:
                cands = [float(df_rt.iloc[last_idx]['High']), curr]
                if today_high is not None: cands.append(today_high)
                df_rt.iloc[last_idx, df_rt.columns.get_loc('High')] = max(cands)
            if 'Low' in df_rt.columns:
                cands = [float(df_rt.iloc[last_idx]['Low']), curr]
                if today_low is not None: cands.append(today_low)
                df_rt.iloc[last_idx, df_rt.columns.get_loc('Low')] = min(cands)
            cci_series = cci(df_rt, 14)
            cci_valid = cci_series.dropna()
            cci14 = float(cci_valid.iloc[-1]) if len(cci_valid)>0 else None
            if cci14 is not None and math.isnan(cci14): cci14=None
        except Exception as e:
            print(f"{code} CCI err {e}")
            cci14=None
        try:
            df_skdj = df_day.copy()
            df_skdj.iloc[-1, df_skdj.columns.get_loc('Close')] = curr
            k_series, d_series = skdj(df_skdj, 9, 6)
            if k_series is not None:
                k_list = [round(float(x),2) for x in k_series.iloc[-60:].tolist() if not pd.isna(x)]
                d_list = [round(float(x),2) for x in d_series.iloc[-60:].tolist() if not pd.isna(x)]
            else:
                k_list=[]; d_list=[]
        except:
            k_list=[]; d_list=[]
        
        results.append({"code":code,"name":name,"display":display,"today":today,"yesterday":yesterday,"pre":pre,"curr":round(curr,2),"pct":round(pct,2),"d20":round(d20_t,2),"d60":round(d60_t,2),"d240":round(d240_t,2),"h20":round(h20_t,2),"h60":round(h60_t,2),"h240":round(h240_t,2),"rsi14":rsi14,"cci14":cci14,"skdj_k":k_list,"skdj_d":d_list})
    except Exception as e:
        print(f"{code} err {e}")
        import traceback; traceback.print_exc()
        results.append({"code":code,"name":name,"display":format_display(code, CN_NAME_MAP.get(code, name)),"today":"白","yesterday":"白","pre":"白","curr":0,"pct":0,"d20":0,"d60":0,"d240":0,"h20":0,"h60":0,"h240":0,"rsi14":None,"cci14":None,"skdj_k":[],"skdj_d":[]})

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
    if val==0 or (isinstance(val,float) and math.isnan(val)): return f"<span class='ma-item'><span class='ma-w'>{label}(--)</span></span>"
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
        rsi_html=f"<span class='rsi-inline {cls}'>RSI ({v:.0f})</span>"
    cci_html=""
    if r.get('cci14') is not None:
        v=r['cci14']
        cls = "rsi-green" if v>=100 else "rsi-red" if v<=-100 else ""
        cci_html=f"<span class='rsi-inline {cls}'>CCI ({v:.0f})</span>"
    if is_white:
        d_row = f"<div class='ma-row'><span class='ma-w'>限流 日k不足或Yahoo限流</span></div>"
        h_row = f"<div class='ma-row'><span class='ma-w'>稍後重試</span></div>"
    else:
        d_row = f"<div class='ma-row'><span class='ma-w'>日k：</span>{ma_span('MA20', r['d20'], r['curr'])} {ma_span('MA60', r['d60'], r['curr'])} {ma_span('MA240', r['d240'], r['curr'])}</div>"
        h_row = f"<div class='ma-row'><span class='ma-w'>時k：</span>{ma_span('MA20', r['h20'], r['curr'])} {ma_span('MA60', r['h60'], r['curr'])} {ma_span('MA240', r['h240'], r['curr'])}</div>"
    display = r.get('display', f"({r['code']}){r['name']}")
    skdj_k_json = json.dumps(r.get('skdj_k',[]))
    skdj_d_json = json.dumps(r.get('skdj_d',[]))
    skdj_box = f"<div class='skdj-box' data-k='{skdj_k_json}' data-d='{skdj_d_json}' title='SKDJ 9 6 滾輪放大'><canvas class='skdj-canvas' width='340' height='56'></canvas></div>" if r.get('skdj_k') and len(r.get('skdj_k'))>5 else ""
    cards+=f"""
<div class="card {r['today']}" data-code="{r['code'].lower()}" data-name="{display.lower()} {r['code'].lower()}" data-ticker="{r['code']}" data-yahoo="https://hk.finance.yahoo.com/quote/{r['code']}/">
  <div class="left">
    <div class="top"><b title="{display}">{display}</b><div class="top-right"><div class="dots-wrap">{dots}</div><div class="star" data-pin='{r['code']}'>☆</div></div></div>
    <div class="mid">{curr_html} {pct_html} {rsi_html}{cci_html}</div>
    <div class="ma-box" data-ticker='{r['code']}'><div class="ma-inner">{d_row}{h_row}</div></div>
    {skdj_box}
  </div>
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
#yahooSuggest .local-tag{font-size:10px;background:#e8f0fe;color:#1a73e8;padding:1px 4px;border-radius:3px;margin-left:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px;align-items:start;min-height:20px}
.section{margin-top:18px} 
.section-title{font-size:13px;color:#c4b5fd;margin:0 0 8px;padding-left:10px;border-left:4px solid #a855f7;position:relative;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.section-title::before{content:'';position:absolute;left:-4px;top:0;bottom:0;width:4px;background:linear-gradient(180deg,#ec4899,#8b5cf6,#3b82f6);border-radius:2px;opacity:0.9}
.section-counts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.count-pill{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:16px;background:#1e293b;border:1px solid #334155;font-size:11px;color:#cbd5e1}
.count-pill .dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex-shrink:0}
.count-pill b{color:#facc15;font-weight:900}
.count-pill.orange .dot{background:#ff8a00} .count-pill.green .dot{background:#00c853} .count-pill.blue .dot{background:#2962ff} .count-pill.red .dot{background:#ef4444} .count-pill.gray .dot{background:#94a3b8}
.count-pill.white-pill{border:3px solid #facc15 !important} .count-pill.white-pill .dot{background:#fff;border:1px solid #000}
.pinned-section{margin-bottom:14px} .pinned-title{font-size:13px;color:#fde68a;margin:0 0 8px;display:none} .pinned-title.show{display:block}
.card{border-radius:14px;padding:11px 13px;display:flex;justify-content:space-between;align-items:flex-start;gap:10px;min-height:175px;overflow:hidden;position:relative;cursor:pointer;transition:transform 0.1s} .card:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,0.3)}
.card.hide{display:none} .sortable-ghost{opacity:0.3} .sortable-chosen{border:2px solid #f59e0b !important}
.card.pinned-clone{border:2px solid #f59e0b;box-shadow:0 0 0 2px rgba(245,158,11,0.2)}
.橙{background:linear-gradient(135deg,#ff8a00,#ffb347);color:#000} .綠{background:linear-gradient(135deg,#00c853,#69f0ae);color:#000} .灰{background:#1e293b;color:#cbd5e1;border:1px solid #2a3441} .藍{background:linear-gradient(135deg,#2962ff,#82b1ff);color:#fff} .紅{background:linear-gradient(135deg,#d50000,#ff5252);color:#fff} .白{background:#fff;color:#000;border:3px dashed #facc15}
.star{font-size:20px;cursor:pointer;user-select:none;line-height:1;padding:4px 6px;border-radius:6px;flex-shrink:0;background:rgba(0,0,0,0.12);width:28px;height:28px;display:flex;align-items:center;justify-content:center} .star:hover{background:rgba(0,0,0,0.25)} .star.pinned{color:#f59e0b} .白 .star{background:rgba(0,0,0,0.06)}
.left{flex:1;min-width:0} 
.top{font-size:12px;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:nowrap;width:100%} .top b{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block;flex-shrink:1} 
.top-right{display:flex;align-items:center;gap:8px;flex-shrink:0;margin-left:auto}
.dots-wrap{display:flex;align-items:center}
.mid{margin-top:6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.price{color:#facc15;font-weight:900;font-size:15px;background:rgba(0,0,0,0.32);padding:2px 8px;border-radius:6px} .白 .price{background:#000;color:#fff}
.pct{font-size:11px;font-weight:800;padding:3px 8px;border-radius:6px;background:rgba(0,0,0,0.45);color:#fff} .pct-up{color:#4ade80} .pct-down{color:#f87171}
.dots{display:inline-flex;align-items:center;background:#000;padding:4px 10px;border-radius:12px;gap:4px;cursor:pointer;user-select:none;border:1px solid #111;flex-shrink:0} .dots.white{background:#fff !important;border-color:#ddd} .dots .arrow{font-size:10px;color:#fff} .dots.white .arrow{color:#000} .dot{width:9px;height:9px;border-radius:50%;display:inline-block} .dot.橙{background:#ff8a00} .dot.綠{background:#00c853} .dot.藍{background:#2962ff} .dot.紅{background:#d50000} .dot.灰{background:#94a3b8} .dot.白{background:#fff;border:1px solid #000}
.rsi-inline{font-size:11px;font-weight:800;padding:3px 7px;border-radius:6px;background:rgba(0,0,0,0.35);margin-left:2px} .rsi-inline.rsi-green{color:#4ade80;border:1px solid #22c55e} .rsi-inline.rsi-red{color:#f87171;border:1px solid #ef4444}
.ma-box{margin-top:6px;background:#000;border-radius:8px;padding:7px 9px;border:1px solid #111;cursor:pointer;overflow:hidden} .ma-box.white{background:#fff;border-color:#ddd} 
.ma-row{font-size:11px;line-height:1.7;display:flex;flex-wrap:nowrap;gap:6px;white-space:nowrap;overflow:hidden} 
.ma-w{color:#fff;font-weight:600;flex-shrink:0} .ma-box.white .ma-w{color:#000 !important} .ma-item{white-space:nowrap;flex-shrink:0} 
.ma-green{color:#4ade80;font-weight:900} .ma-red{color:#f87171;font-weight:900} .ma-same{color:#fff} .ma-box.white .ma-same{color:#000}
.skdj-box{margin-top:6px;background:#111;border-radius:8px;padding:2px 6px 2px;border:1px solid #222;position:relative;height:60px;overflow:hidden;cursor:ns-resize}
.skdj-box canvas{width:100%;height:56px;display:block}
.skdj-box.white{background:#fff;border-color:#ddd}
.skdj-legend{position:absolute;top:2px;left:6px;right:6px;display:flex;justify-content:space-between;font-size:9px;pointer-events:none}
.skdj-legend-left{display:flex;gap:6px;align-items:center}
.skdj-legend-right{display:flex;gap:8px;align-items:center}
.skdj-legend .skdj-title{color:#888;background:rgba(0,0,0,0.6);padding:1px 4px;border-radius:3px}
.skdj-legend .skdj-val-k{color:#3b82f6;font-weight:700}
.skdj-legend .skdj-val-d{color:#22c55e;font-weight:700}
.search{flex:1;min-width:120px;max-width:320px} .addRow input{flex:1} .ver{background:#78350f;color:#fde68a;border:1px solid #92400e;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:800}
.info-box{position:relative;background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px;margin:14px 0;font-size:11px;line-height:1.8}
.rocket-btn{position:absolute;right:12px;bottom:12px;background:#ffffff;color:#000;border:1px solid #e5e7eb;border-radius:8px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:18px;font-weight:900;box-shadow:0 2px 8px rgba(0,0,0,0.3)}
.rocket-btn:hover{background:#f3f4f6}
.export-btn{background:#000 !important;color:#fff !important;border:1px solid #333 !important}
.export-btn:hover{background:#111 !important}
</style></head><body>

<div id="lock">
<h2>🔒 私有看板</h2>
<div style="color:#94a3b8;font-size:13px">請輸入密碼</div>
<input id="pw" type="password" placeholder="請輸入密碼" autocomplete="off"/>
<button id="enterBtn" type="button">進入</button>
<div id="lockMsg" style="color:#f87171;font-size:13px;margin-top:12px;min-height:20px;font-weight:700"></div>
</div>

<div class="header" id="headerRow" style="display:flex;align-items:center;justify-content:space-between;width:100%;max-width:1200px;gap:12px;flex-wrap:nowrap;box-sizing:border-box">
<h1 style="display:flex;align-items:center;gap:8px;flex-wrap:nowrap"><a href="https://hk.finance.yahoo.com/markets" target="_blank" style="text-decoration:none;display:inline-flex;align-items:center" title="Yahoo HK"><img src="data:image/png;base64,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" style="margin-right:6px;width:32px;height:32px;border-radius:50%;object-fit:cover;display:inline-block;vertical-align:middle;filter:drop-shadow(0 0 2px rgba(255,255,255,0.3))" alt="moon" /></a> MA(20/60/240) 私有版 <span class="ver" style="background:#92400e;color:#fff;padding:2px 8px;border-radius:8px;font-size:12px">V58</span>
<div class="search" style="margin-left:12px"><span class="icon">🔍</span><input id="search" type="text" placeholder="搜索代號/名稱" /></div>
</h1>
<div style="display:flex;align-items:center;gap:10px;margin-left:auto">
<button id="rocketTopBtn" title="到最底部" style="background:none;border:none;cursor:pointer;font-size:24px;line-height:1;padding:6px 10px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center">🚀</button>
</div>
</div>

<div class="addRow" id="addRow" style="width:100%;max-width:1200px;box-sizing:border-box;display:flex;gap:10px;align-items:center"><input id="addInput" type="text" placeholder="加股：輸入自動出現選單" autocomplete="off"/><div id="yahooSuggest"></div><button class="addbtn" id="addBtn">+ 加股</button><button class="addbtn" id="clearBtn" style="background:#1e293b;color:#fff;border:1px solid #334155">清空自加</button></div>

<div class="sub" id="subRow" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;width:100%;max-width:1200px;box-sizing:border-box;margin-top:10px">更新: __UPDATE_TIME__ 香港時間 | 共<span id="count">__COUNT__</span>隻 自加<span id="customCount">0</span>隻 置頂<span id="pinCount">0</span>隻 |
<button id="filterUpBtn" style="padding:4px 12px;border-radius:8px;font-size:12px;font-weight:900;border:none;cursor:pointer;background:#16a34a;color:#fff">漲0隻</button>
<button id="filterDownBtn" style="padding:4px 12px;border-radius:8px;font-size:12px;font-weight:900;border:none;cursor:pointer;background:#dc2626;color:#fff">跌0隻</button>
<button id="filterAllBtn" style="padding:4px 12px;border-radius:8px;font-size:12px;font-weight:900;border:none;cursor:pointer;background:linear-gradient(135deg,#c084fc,#f472b6);color:#fff">全部</button>
</div>

<div class="pinned-section"><div id="pinnedTitle" class="pinned-title">⭐ 置頂觀察</div><div id="pinnedGrid" class="grid"></div></div>

<div class="section"><div class="section-title" id="defaultTitle"><div class="section-counts" id="defaultCounts"></div></div><div class="grid" id="grid">__CARDS__</div></div>

<div class="section"><div class="section-title">.HK</div><div class="grid" id="grid-hk"></div></div>
<div class="section"><div class="section-title">指數</div><div class="grid" id="grid-index"></div></div>
<div class="section"><div class="section-title">等候 (自加待建 custom.json)</div><div class="grid" id="grid-waiting"></div></div>

<div class="info-box">
<b>技術指標MA(20，60，240) 實時含盤前後 延長時段：</b><br>
🟠 股價日k站上MA60，時k站上MA60和MA240。<br>
🟢 股價日k站上MA20，時k站上MA60。<br>
🔵 股價日k跌穿MA20，時k跌穿MA20。<br>
🔴 股價日k跌穿MA60，時k跌穿MA60。<br>
⚪ 不符合以上條件。<br>
⬜ 白=限流 ⭐ 點星星置頂<br><br>
<button id="exportBtn" class="export-btn" style="padding:8px 14px;border-radius:8px;border:none;font-weight:800;cursor:pointer">📋 匯出自加清單</button>
<button id="saveAllBtn" class="export-btn" style="padding:8px 14px;border-radius:8px;border:none;font-weight:800;cursor:pointer;margin-left:8px">💾 保存卡片+排序</button>
<button id="importAllBtn" class="export-btn" style="padding:8px 14px;border-radius:8px;border:none;font-weight:800;cursor:pointer;margin-left:8px">📥 匯入卡片+排序</button>
<input type="file" id="importFile" accept=".json" style="display:none" />
<button class="rocket-btn" id="rocketBtn" title="返回頂部">🚀</button>
</div>

<script>
(function(){
  var REAL_PW = "88666666";
  function doUnlock(){
    var input = document.getElementById('pw');
    var msg = document.getElementById('lockMsg');
    var v = (input.value||'').trim();
    if(!v){ msg.textContent="請輸入密碼"; return; }
    if(v === REAL_PW){ document.getElementById('lock').style.display='none'; msg.textContent=""; try{ sessionStorage.setItem('ma_pw','ok'); }catch(e){} }
    else{ msg.textContent="❌ 密碼錯誤"; input.value=""; input.focus(); input.style.borderColor="#ef4444"; setTimeout(function(){ input.style.borderColor="#334155"; }, 2000); }
  }
  document.addEventListener('DOMContentLoaded', function(){
    var btn = document.getElementById('enterBtn'); var pw = document.getElementById('pw');
    if(btn){ btn.addEventListener('click', doUnlock); btn.onclick = doUnlock; }
    if(pw){ pw.addEventListener('keydown', function(e){ if(e.key==='Enter'){ e.preventDefault(); doUnlock(); } }); pw.focus(); }
    try{ if(sessionStorage.getItem('ma_pw')==='ok'){ document.getElementById('lock').style.display='none'; } }catch(e){}
  });
})();
var LAYOUT_KEY = "ma_board_layout_permanent"; var PIN_KEY = "ma_board_pins_permanent"; var FOCUS_DOTS_KEY = "ma_board_focus_dots"; var FOCUS_MA_KEY = "ma_board_focus_ma"; var CUSTOM_KEY = "ma_board_custom_permanent";
function getLayoutKey(){ var oldKeys = ["layoutOrderV34","layoutOrderV33","layoutOrderV32","layoutOrderV31","layoutOrderV30"]; var oldData = null; for(var i=0;i<oldKeys.length;i++){ try{ var d = localStorage.getItem(oldKeys[i]); if(d){ oldData = d; break; } }catch(e){} } if(oldData && !localStorage.getItem(LAYOUT_KEY)){ localStorage.setItem(LAYOUT_KEY, oldData); } return LAYOUT_KEY; }
var focusDots = JSON.parse(localStorage.getItem(FOCUS_DOTS_KEY)||'{}'); var focusMa = JSON.parse(localStorage.getItem(FOCUS_MA_KEY)||'{}');
document.addEventListener('click', function(e){
  if(e.target.closest('.skdj-box')){ e.stopPropagation(); return; }
  var star = e.target.closest('.star'); if(star){ e.stopPropagation(); var ticker=star.getAttribute('data-pin'); if(ticker) togglePin(ticker); return; }
  var dots = e.target.closest('.dots'); if(dots){ e.stopPropagation(); var t=dots.getAttribute('data-ticker'); var newWhite = !dots.classList.contains('white'); document.querySelectorAll('.card[data-ticker="'+t+'"]').forEach(function(c){ c.querySelectorAll('.dots[data-ticker="'+t+'"]').forEach(function(d){ if(newWhite) d.classList.add('white'); else d.classList.remove('white'); }); }); if(t){ if(newWhite) focusDots[t]=1; else delete focusDots[t]; localStorage.setItem(FOCUS_DOTS_KEY, JSON.stringify(focusDots)); } return; }
  var mbox = e.target.closest('.ma-box'); if(mbox){ e.stopPropagation(); var t=mbox.getAttribute('data-ticker'); var newWhite = !mbox.classList.contains('white'); document.querySelectorAll('.card[data-ticker="'+t+'"]').forEach(function(c){ c.querySelectorAll('.ma-box[data-ticker="'+t+'"]').forEach(function(m){ if(newWhite) m.classList.add('white'); else m.classList.remove('white'); }); c.querySelectorAll('.skdj-box').forEach(function(s){ if(newWhite) s.classList.add('white'); else s.classList.remove('white'); }); }); if(t){ if(newWhite) focusMa[t]=1; else delete focusMa[t]; localStorage.setItem(FOCUS_MA_KEY, JSON.stringify(focusMa)); } return; }
});
document.addEventListener('dblclick', function(e){ var card = e.target.closest('.card'); if(card){ if(card.classList.contains('sortable-chosen')) return; if(e.target.closest('.star') || e.target.closest('.dots') || e.target.closest('.ma-box') || e.target.closest('.skdj-box')) return; var yahooUrl = card.getAttribute('data-yahoo'); if(yahooUrl){ window.open(yahooUrl, '_blank'); } } });
function applyFocus(){ document.querySelectorAll('.dots[data-ticker]').forEach(function(el){ if(focusDots[el.getAttribute('data-ticker')]) el.classList.add('white'); }); document.querySelectorAll('.ma-box[data-ticker]').forEach(function(el){ if(focusMa[el.getAttribute('data-ticker')]) el.classList.add('white'); }); document.querySelectorAll('.skdj-box').forEach(function(el){ var t = el.closest('.card').getAttribute('data-ticker'); if(focusMa[t]) el.classList.add('white'); }); }
function saveLayout(){ var order={}; ['grid','pinnedGrid','grid-hk','grid-index','grid-waiting'].forEach(function(id){ var el=document.getElementById(id); if(!el) return; order[id]=Array.from(el.children).map(function(c){return c.getAttribute('data-ticker')}).filter(Boolean); }); localStorage.setItem(getLayoutKey(), JSON.stringify(order)); if(order['pinnedGrid']){ pinnedStocks = order['pinnedGrid'].map(function(t){return t.toUpperCase();}); localStorage.setItem(getPinKey(), JSON.stringify(pinnedStocks)); } }
function initSortable(){ ['grid','pinnedGrid','grid-hk','grid-index','grid-waiting'].forEach(function(id){ var el=document.getElementById(id); if(!el) return; if(el._sortable) el._sortable.destroy(); el._sortable = new Sortable(el, { group: 'shared', animation:150, ghostClass:'sortable-ghost', chosenClass:'sortable-chosen', onStart: function(){ document.body.classList.add('dragging'); }, onEnd: function(){ setTimeout(function(){ document.body.classList.remove('dragging'); }, 100); saveLayout(); renderPins(); }}); }); }
function restoreLayout(){ try{ var orderStr = localStorage.getItem(getLayoutKey()); if(!orderStr){ var oldKeys = ["layoutOrderV34","layoutOrderV33","layoutOrderV32","layoutOrderV31","layoutOrderV30"]; for(var i=0;i<oldKeys.length;i++){ var d = localStorage.getItem(oldKeys[i]); if(d){ orderStr = d; localStorage.setItem(getLayoutKey(), d); break; } } } if(!orderStr) return; var order=JSON.parse(orderStr); Object.keys(order).forEach(function(gridId){ if(gridId==='pinnedGrid') return; var grid=document.getElementById(gridId); if(!grid) return; var map={}; document.querySelectorAll('#grid .card, #grid-hk .card, #grid-index .card, #grid-waiting .card').forEach(function(c){ if(!c.classList.contains('pinned-clone')) map[c.getAttribute('data-ticker').toUpperCase()]=c; }); (order[gridId]||[]).forEach(function(t){ var card=map[t.toUpperCase()]; if(card) grid.appendChild(card); }); }); if(order['pinnedGrid'] && order['pinnedGrid'].length>0){ var pinnedGrid=document.getElementById('pinnedGrid'); var existingMap={}; pinnedGrid.querySelectorAll('.card').forEach(function(c){ existingMap[c.getAttribute('data-ticker').toUpperCase()]=c; }); document.querySelectorAll('#grid .card, #grid-hk .card, #grid-index .card, #grid-waiting .card').forEach(function(c){ var tk=c.getAttribute('data-ticker').toUpperCase(); if(!existingMap[tk]) existingMap[tk]=c; }); order['pinnedGrid'].forEach(function(t){ var card=existingMap[t.toUpperCase()]; if(card){ var clone=card.cloneNode(true); if(!card.classList.contains('pinned-clone')){ clone.classList.add('pinned-clone'); var star=clone.querySelector('.star'); if(star) star.textContent='★'; } pinnedGrid.appendChild(clone); var skBox=clone.querySelector('.skdj-box'); if(skBox) initSkdjBox(skBox); } }); pinnedStocks = order['pinnedGrid'].map(function(t){return t.toUpperCase();}); localStorage.setItem(getPinKey(), JSON.stringify(pinnedStocks)); } }catch(e){ console.log('restore err', e); } }
function getPinKey(){ var oldPinKeys = ["pinnedV34","pinnedV33","pinnedV32","pinnedV31","pinnedV30"]; for(var i=0;i<oldPinKeys.length;i++){ var d = localStorage.getItem(oldPinKeys[i]); if(d && !localStorage.getItem(PIN_KEY)){ localStorage.setItem(PIN_KEY, d); break; } } return PIN_KEY; }
var pinnedStocks = JSON.parse(localStorage.getItem(getPinKey())||'[]');
function togglePin(ticker){
  ticker=ticker.toUpperCase();
  var pinnedGrid = document.getElementById('pinnedGrid');
  var isPinned = pinnedStocks.includes(ticker);
  if(isPinned){
    pinnedStocks = pinnedStocks.filter(function(t){return t!==ticker});
    var clone = pinnedGrid.querySelector('.card[data-ticker="'+ticker+'"]');
    if(clone) clone.remove();
  } else {
    var original = document.querySelector('#grid .card[data-ticker="'+ticker+'"], #grid-hk .card[data-ticker="'+ticker+'"], #grid-index .card[data-ticker="'+ticker+'"], #grid-waiting .card[data-ticker="'+ticker+'"]');
    if(!original){ original = document.querySelector('.card[data-ticker="'+ticker+'"]:not(.pinned-clone)'); }
    if(original){
      var clone = original.cloneNode(true);
      clone.classList.add('pinned-clone');
      var star = clone.querySelector('.star');
      if(star) star.textContent = '★';
      pinnedGrid.appendChild(clone);
      pinnedStocks.push(ticker);
      var skBox = clone.querySelector('.skdj-box');
      if(skBox) initSkdjBox(skBox);
    }
  }
  localStorage.setItem(getPinKey(), JSON.stringify(pinnedStocks));
  renderPins(); saveLayout(); applyFocus();
}
function renderPins(){
  var pinnedGrid = document.getElementById('pinnedGrid');
  var count = pinnedStocks.length;
  document.getElementById('pinnedTitle').classList.toggle('show', count>0);
  document.getElementById('pinCount').innerText=count;
  pinnedGrid.querySelectorAll('.card').forEach(function(c){ var t = c.getAttribute('data-ticker').toUpperCase(); if(!pinnedStocks.includes(t)) c.remove(); });
  pinnedStocks.forEach(function(ticker){ if(!pinnedGrid.querySelector('.card[data-ticker="'+ticker+'"]')){ var original = document.querySelector('.card[data-ticker="'+ticker+'"]:not(.pinned-clone)'); if(original){ var clone = original.cloneNode(true); clone.classList.add('pinned-clone'); var star = clone.querySelector('.star'); if(star) star.textContent = '★'; pinnedGrid.appendChild(clone); var skBox = clone.querySelector('.skdj-box'); if(skBox) initSkdjBox(skBox); } } });
  document.querySelectorAll('.card:not(.pinned-clone)').forEach(function(card){ var t=card.getAttribute('data-ticker').toUpperCase(); var s=card.querySelector('.star'); if(!s) return; var isPinned = pinnedStocks.includes(t); s.innerText=isPinned?'★':'☆'; s.classList.toggle('pinned', isPinned); });
  pinnedGrid.querySelectorAll('.star').forEach(function(s){ s.innerText='★'; s.classList.add('pinned'); });
}
function autoFitMaBox(box){
  if(!box) return;
  var inner = box.querySelector('.ma-inner');
  if(!inner) return;
  var rows = inner.querySelectorAll('.ma-row');
  if(rows.length===0) return;
  var sizes = [13, 12.5, 12, 11.5, 11, 10.5, 10, 9.5, 9, 8.5, 8];
  var boxW = box.clientWidth - 18;
  if(boxW<=0) boxW = 300;
  for(var i=0;i<sizes.length;i++){
    var sz = sizes[i];
    var ok = true;
    rows.forEach(function(row){
      row.style.fontSize = sz + 'px';
      if(row.scrollWidth > boxW + 2) ok = false;
      if(row.clientHeight > 22) ok = false;
    });
    if(ok){ return; }
  }
  rows.forEach(function(row){ row.style.fontSize = '8px'; });
}
function autoFitAllMa(){ document.querySelectorAll('.ma-box').forEach(function(box){ autoFitMaBox(box); }); }
function initSkdjBox(box){
  if(!box) return;
  try{
    var kData = JSON.parse(box.getAttribute('data-k')||'[]');
    var dData = JSON.parse(box.getAttribute('data-d')||'[]');
    if(kData.length===0) return;
    var canvas = box.querySelector('canvas');
    if(!canvas) return;
    var ctx = canvas.getContext('2d');
    var w = canvas.width, h = canvas.height;
    var showDays = box._showDays || 30;
    if(showDays<10) showDays=10;
    if(showDays>kData.length) showDays=kData.length;
    box._showDays = showDays;
    var kSlice = kData.slice(-showDays);
    var dSlice = dData.slice(-showDays);
    ctx.clearRect(0,0,w,h);
    ctx.fillStyle = box.classList.contains('white') ? '#f5f5f5' : '#0a0a0a';
    ctx.fillRect(0,0,w,h);
    ctx.fillStyle = box.classList.contains('white') ? 'rgba(255,200,200,0.35)' : 'rgba(80,20,20,0.4)';
    ctx.fillRect(0,0,w,h*0.25);
    ctx.fillStyle = box.classList.contains('white') ? 'rgba(200,255,200,0.35)' : 'rgba(20,60,20,0.4)';
    ctx.fillRect(0,h*0.75,w,h*0.25);
    ctx.strokeStyle = '#666'; ctx.setLineDash([4,4]); ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.moveTo(0, h*0.25); ctx.lineTo(w, h*0.25); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, h*0.75); ctx.lineTo(w, h*0.75); ctx.stroke();
    ctx.setLineDash([]); ctx.strokeStyle = '#444'; ctx.setLineDash([2,6]); ctx.beginPath(); ctx.moveTo(0, h*0.5); ctx.lineTo(w, h*0.5); ctx.stroke(); ctx.setLineDash([]);
    function drawLine(data, color){ ctx.strokeStyle = color; ctx.lineWidth = 1.6; ctx.beginPath(); data.forEach(function(v,i){ var x = (i/(data.length-1))*w; var y = h - (v/100)*h; if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); }); ctx.stroke(); }
    drawLine(kSlice, '#3b82f6'); drawLine(dSlice, '#22c55e');
    for(var i=1;i<kSlice.length;i++){
      var prevK = kSlice[i-1], prevD = dSlice[i-1]; var curK = kSlice[i], curD = dSlice[i];
      if(prevK<=prevD && curK>prevD){ var x = (i/(kSlice.length-1))*w; var y = h - (curK/100)*h; ctx.fillStyle = '#22c55e'; ctx.beginPath(); ctx.arc(x,y,3,0,Math.PI*2); ctx.fill(); }
      else if(prevK>=prevD && curK<prevD){ var x = (i/(kSlice.length-1))*w; var y = h - (curK/100)*h; ctx.fillStyle = '#ef4444'; ctx.beginPath(); ctx.arc(x,y,3,0,Math.PI*2); ctx.fill(); }
    }
    var lastK = kSlice[kSlice.length-1]; var lastD = dSlice[dSlice.length-1];
    var oldLeg = box.querySelector('.skdj-legend'); if(oldLeg) oldLeg.remove();
    var leg = document.createElement('div'); leg.className='skdj-legend';
    leg.innerHTML = '<div class="skdj-legend-left"><span class="skdj-title">SKDJ 9 6</span></div><div class="skdj-legend-right"><span class="skdj-val-k">'+lastK.toFixed(2)+'</span><span class="skdj-val-d">'+lastD.toFixed(2)+'</span></div>';
    box.appendChild(leg);
  }catch(e){ console.log('skdj err', e); }
}
function initAllSkdj(){
  document.querySelectorAll('.skdj-box').forEach(function(box){ initSkdjBox(box); });
  document.querySelectorAll('.skdj-box').forEach(function(box){
    box.addEventListener('wheel', function(e){
      e.preventDefault(); e.stopPropagation();
      var delta = e.deltaY > 0 ? 5 : -5; var cur = box._showDays || 30; cur += delta; if(cur<10) cur=10; var kData = JSON.parse(box.getAttribute('data-k')||'[]'); if(cur>kData.length) cur=kData.length; box._showDays = cur; initSkdjBox(box);
    }, {passive:false});
  });
}
function updateSectionCounts(){
  function countGrid(gridIds){
    var c={橙:0,綠:0,藍:0,紅:0,灰:0,白:0};
    gridIds.forEach(function(gridId){
      document.querySelectorAll('#'+gridId+' .card').forEach(function(card){
        if(card.classList.contains('橙')) c.橙++;
        else if(card.classList.contains('綠')) c.綠++;
        else if(card.classList.contains('藍')) c.藍++;
        else if(card.classList.contains('紅')) c.紅++;
        else if(card.classList.contains('灰')) c.灰++;
        else if(card.classList.contains('白')) c.白++;
      });
    });
    return c;
  }
  function renderPills(containerId, counts, isDefault){
    var el=document.getElementById(containerId);
    if(!el) return;
    var html='';
    if(isDefault){
      html+='<span class="count-pill orange"><span class="dot"></span>橙 主升 <b>'+counts.橙+'隻</b></span>';
      html+='<span class="count-pill green"><span class="dot"></span>綠 次強 <b>'+counts.綠+'隻</b></span>';
      html+='<span class="count-pill blue"><span class="dot"></span>藍 弱 <b>'+counts.藍+'隻</b></span>';
      html+='<span class="count-pill red"><span class="dot"></span>紅 空頭 <b>'+counts.紅+'隻</b></span>';
      html+='<span class="count-pill gray"><span class="dot"></span>灰 震盪 <b>'+counts.灰+'隻</b></span>';
      if(counts.白>0) html+='<span class="count-pill white-pill"><span class="dot"></span>白 限流 <b>'+counts.白+'隻</b></span>';
    }
    el.innerHTML=html;
  }
  var defaultAll = countGrid(['grid','grid-hk','grid-index']);
  renderPills('defaultCounts', defaultAll, true);
}

document.getElementById('search').addEventListener('input', function(e){ var q=e.target.value.trim().toLowerCase(); document.querySelectorAll('.grid .card').forEach(function(card){ var code=card.getAttribute('data-code')||''; var name=card.getAttribute('data-name')||''; if(!q) card.classList.remove('hide'); else card.classList.toggle('hide', !(code.includes(q)||name.includes(q))); }); });
function getCustomKey(){ var oldKeys = ["customStocksV34","customStocksV33","customStocksV32","customStocksV31","customStocksV30"]; for(var i=0;i<oldKeys.length;i++){ var d = localStorage.getItem(oldKeys[i]); if(d && !localStorage.getItem(CUSTOM_KEY)){ localStorage.setItem(CUSTOM_KEY, d); break; } } return CUSTOM_KEY; }
var customStocks = JSON.parse(localStorage.getItem(getCustomKey())||'[]');
function saveCustom(){ localStorage.setItem(getCustomKey(), JSON.stringify(customStocks)); document.getElementById('customCount').innerText=customStocks.length; }
function normalizeTicker(s){ s=s.trim().toUpperCase(); if(!s) return null; if(/^\\d{3,5}$/.test(s)) return s+'.HK'; return s; }
function addStock(input){ var raw=(input||document.getElementById('addInput').value||'').trim(); if(!raw) return; var tok=raw.split(/[\\s,，]+/)[0]; var ticker=normalizeTicker(tok); var name=raw.replace(tok,'').trim()||tok; document.getElementById('addInput').value=''; document.getElementById('yahooSuggest').style.display='none'; if(customStocks.find(function(s){return s.code===ticker})){ alert(ticker+' 已加過'); return; } customStocks.push({code:ticker, name:name}); saveCustom(); var disp='('+ticker+')'+name; if(disp.length>30) disp=disp.slice(0,29)+'...'; document.getElementById('grid-waiting').insertAdjacentHTML('beforeend', '<div class="card 白 custom" data-code="'+ticker.toLowerCase()+'" data-name="'+name.toLowerCase()+'" data-ticker="'+ticker+'" data-yahoo="https://hk.finance.yahoo.com/quote/'+ticker+'/"><div class="left"><div class="top"><b>'+disp+'</b><div class="top-right"><div class="dots-wrap"><span class="dots" data-ticker="'+ticker+'"><span class="dot 白"></span><span class="arrow">→</span><span class="dot 白"></span><span class="arrow">→</span><span class="dot 白"></span></span></div><div class="star" data-pin="'+ticker+'">☆</div></div></div><div class="mid"><span class="price">等候區</span></div></div></div>'); saveLayout(); autoFitAllMa(); updateSectionCounts(); }
document.getElementById('addBtn').addEventListener('click', function(){ addStock(); });
document.getElementById('clearBtn').addEventListener('click', function(){ if(!confirm('清空所有自加？')) return; customStocks=[]; saveCustom(); document.getElementById('grid-waiting').innerHTML=''; saveLayout(); updateSectionCounts(); });
document.getElementById('exportBtn').addEventListener('click', function(){ if(customStocks.length===0){ alert('還沒有自加'); return; } var txt=JSON.stringify(customStocks.map(function(s){return {code:s.code, name:s.name}}), null, 2); navigator.clipboard.writeText(txt).then(function(){alert('已複製 custom.json');}).catch(function(){prompt('複製',txt)}); });
document.getElementById('saveAllBtn').addEventListener('click', function(){ var data={ version:"V58", exportTime: new Date().toISOString(), customStocks: customStocks, layout: JSON.parse(localStorage.getItem(getLayoutKey())||'{}'), pinned: JSON.parse(localStorage.getItem(getPinKey())||'[]'), focusDots: JSON.parse(localStorage.getItem(FOCUS_DOTS_KEY)||'{}'), focusMa: JSON.parse(localStorage.getItem(FOCUS_MA_KEY)||'{}') }; var txt=JSON.stringify(data, null, 2); var blob=new Blob([txt], {type:"application/json"}); var url=URL.createObjectURL(blob); var a=document.createElement('a'); a.href=url; a.download="ma_board_backup_"+new Date().toISOString().slice(0,10)+".json"; document.body.appendChild(a); a.click(); setTimeout(function(){ document.body.removeChild(a); URL.revokeObjectURL(url); }, 100); alert('已保存全部卡片+排序'); });
document.getElementById('importAllBtn').addEventListener('click', function(){ document.getElementById('importFile').click(); });
document.getElementById('importFile').addEventListener('change', function(e){ var file=e.target.files[0]; if(!file) return; var reader=new FileReader(); reader.onload=function(ev){ try{ var data=JSON.parse(ev.target.result); if(!data.customStocks && !data.layout && !data.pinned){ alert('檔案格式不對'); return; } if(!confirm('匯入後會替換當前所有卡片+排序，確定覆蓋？')) return; if(data.customStocks){ localStorage.setItem(getCustomKey(), JSON.stringify(data.customStocks)); } if(data.layout){ localStorage.setItem(getLayoutKey(), JSON.stringify(data.layout)); } if(data.pinned){ localStorage.setItem(getPinKey(), JSON.stringify(data.pinned)); } if(data.focusDots){ localStorage.setItem(FOCUS_DOTS_KEY, JSON.stringify(data.focusDots)); } if(data.focusMa){ localStorage.setItem(FOCUS_MA_KEY, JSON.stringify(data.focusMa)); } alert('匯入成功，頁面將重載'); location.reload(); }catch(err){ alert('匯入失敗：'+err.message); } }; reader.readAsText(file); e.target.value=''; });

document.getElementById('addInput').addEventListener('keydown', function(e){ if(e.key==='Enter'){ var box=document.getElementById('yahooSuggest'); if(box.style.display!=='none' && box.children.length>1){ var firstItem = box.querySelector('.s-item'); if(firstItem) firstItem.click(); } else addStock(); } });
document.getElementById('rocketBtn').addEventListener('click', function(){ window.scrollTo({top:0, behavior:'smooth'}); });
document.getElementById('rocketTopBtn').addEventListener('click', function(){ window.scrollTo({top:document.body.scrollHeight, behavior:'smooth'}); });
var LOCAL_TICKERS = [
  {symbol:"AAPL", name:"蘋果", type:"股票"}, {symbol:"TSLA", name:"特斯拉", type:"股票"}, {symbol:"NVDA", name:"英偉達", type:"股票"}, {symbol:"MSFT", name:"微軟", type:"股票"}, {symbol:"GOOGL", name:"谷歌-A", type:"股票"}, {symbol:"GOOG", name:"谷歌-C", type:"股票"}, {symbol:"AMZN", name:"亞馬遜", type:"股票"}, {symbol:"META", name:"Meta", type:"股票"}, {symbol:"AMD", name:"超微半導體", type:"股票"}, {symbol:"INTC", name:"英特爾", type:"股票"}, {symbol:"MU", name:"美光科技", type:"股票"}, {symbol:"SMCI", name:"超微電腦", type:"股票"}, {symbol:"BABA", name:"阿里巴巴", type:"股票"}, {symbol:"NIO", name:"蔚來", type:"股票"}, {symbol:"LI", name:"理想汽車", type:"股票"}, {symbol:"XPEV", name:"小鵬汽車", type:"股票"}, {symbol:"BIDU", name:"百度", type:"股票"}, {symbol:"FUTU", name:"富途控股", type:"股票"}, {symbol:"TSM", name:"台積電", type:"股票"}, {symbol:"AVGO", name:"博通", type:"股票"}, {symbol:"TSLL", name:"Direxion Daily TSLA Bull 2X", type:"ETF"}, {symbol:"TSLQ", name:"Tradr 2X Short TSLA Daily", type:"ETF"}, {symbol:"TSL", name:"GraniteShares 1.25x Long Tsla Daily", type:"ETF"}, {symbol:"SOXL", name:"半導體3X", type:"ETF"}, {symbol:"SOXX", name:"半導體ETF", type:"ETF"}, {symbol:"TQQQ", name:"納指3X", type:"ETF"}, {symbol:"SQQQ", name:"納指3X空", type:"ETF"}, {symbol:"SPY", name:"標普500ETF", type:"ETF"}, {symbol:"QQQ", name:"納指ETF", type:"ETF"}, {symbol:"UPRO", name:"標普3X", type:"ETF"}, {symbol:"01810.HK", name:"小米集團-W", type:"股票"}, {symbol:"09988.HK", name:"阿里巴巴-W", type:"股票"}, {symbol:"BTC-USD", name:"比特幣", type:"加密貨幣"}, {symbol:"ETH-USD", name:"以太坊", type:"加密貨幣"}, {symbol:"^GSPC", name:"標普500指數", type:"指數"}, {symbol:"^IXIC", name:"納斯達克", type:"指數"}, {symbol:"^DJI", name:"道瓊工業", type:"指數"}, {symbol:"^HSI", name:"恒生指數", type:"指數"},
];
var yTimer=null; var yahooCache={}; var yahooSuggest=document.getElementById('yahooSuggest');
function renderLocalResults(q){ var qUpper = q.toUpperCase(); var matched = LOCAL_TICKERS.filter(function(item){ return item.symbol.toUpperCase().indexOf(qUpper)>=0; }).slice(0, 8); if(matched.length===0) return false; yahooSuggest.innerHTML='<div class="s-head"><span>股票代號</span><span>即時匹配</span></div>'; matched.forEach(function(it){ var div=document.createElement('div'); div.className='s-item'; div.innerHTML='<div class="s-row1"><span class="s-code">'+it.symbol+'</span><span class="s-type">'+it.type+'<span class="local-tag">本地</span></span></div><div class="s-name">'+it.name+'</div>'; div.onclick=function(){ document.getElementById('addInput').value=it.symbol+' '+it.name; yahooSuggest.style.display='none'; addStock(it.symbol+' '+it.name); }; yahooSuggest.appendChild(div); }); yahooSuggest.style.display='block'; return true; }
function renderYahooResults(quotes){ if(!quotes || quotes.length===0) return; var hasHead = yahooSuggest.querySelector('.s-head'); if(!hasHead){ yahooSuggest.innerHTML='<div class="s-head"><span>股票代號</span><span>Yahoo 財經</span></div>'; } else { var existingSyms = {}; yahooSuggest.querySelectorAll('.s-code').forEach(function(el){ existingSyms[el.textContent]=1; }); quotes = quotes.filter(function(it){ return !existingSyms[it.symbol]; }); } quotes.forEach(function(it){ var sym=it.symbol||''; var name=it.shortname||it.longname||sym; if(name.indexOf('來自 Yahoo')>=0) name=sym; var typeLabel=it.quoteType==='ETF'?'ETF':(it.quoteType==='EQUITY'?'股票':(it.exchange||'')); var div=document.createElement('div'); div.className='s-item'; div.innerHTML='<div class="s-row1"><span class="s-code">'+sym+'</span><span class="s-type">'+typeLabel+'</span></div><div class="s-name">'+name+'</div>'; div.onclick=function(){ document.getElementById('addInput').value=sym+' '+name; yahooSuggest.style.display='none'; addStock(sym+' '+name); }; yahooSuggest.appendChild(div); }); yahooSuggest.style.display='block'; }
document.getElementById('addInput').addEventListener('input', function(e){ var q=e.target.value.trim(); if(!q || q.length<1){ yahooSuggest.style.display='none'; return; } clearTimeout(yTimer); var hasLocal = renderLocalResults(q); yTimer=setTimeout(function(){ if(yahooCache[q]){ renderYahooResults(yahooCache[q]); return; } var yUrl='https://query1.finance.yahoo.com/v1/finance/search?q='+encodeURIComponent(q)+'&quotesCount=12&newsCount=0&lang=zh-Hant&region=HK'; var proxies=['https://api.allorigins.win/raw?url='+encodeURIComponent(yUrl),'https://corsproxy.io/?'+encodeURIComponent(yUrl)]; var done=false; var tryFetch = function(url){ fetch(url, {cache:'no-store'}).then(function(r){ return r.json(); }).then(function(data){ if(done) return; if(!data || !data.quotes || data.quotes.length===0) return; done=true; yahooCache[q]=data.quotes; renderYahooResults(data.quotes); }).catch(function(){}); }; proxies.forEach(function(p){ tryFetch(p); }); }, hasLocal ? 300 : 80); });
document.addEventListener('click', function(e){ if(!e.target.closest('.addRow')) yahooSuggest.style.display='none'; });
(function(){ saveCustom(); var waiting=document.getElementById('grid-waiting'); customStocks.forEach(function(s){ var id='custom-'+s.code.replace(/\\./g,'-'); if(document.getElementById(id)) return; var exists=false; document.querySelectorAll('#grid .card').forEach(function(c){ if(c.getAttribute('data-ticker')===s.code) exists=true; }); if(exists) return; var disp='('+s.code+')'+s.name; if(disp.length>30) disp=disp.slice(0,29)+'...'; waiting.insertAdjacentHTML('beforeend', '<div class="card 白 custom" id="'+id+'" data-code="'+s.code.toLowerCase()+'" data-name="'+s.name.toLowerCase()+'" data-ticker="'+s.code+'" data-yahoo="https://hk.finance.yahoo.com/quote/'+s.code+'/"><div class="left"><div class="top"><b>'+disp+'</b><div class="top-right"><div class="dots-wrap"><span class="dots" data-ticker="'+s.code+'"><span class="dot 白"></span><span class="arrow">→</span><span class="dot 白"></span><span class="arrow">→</span><span class="dot 白"></span></span></div><div class="star" data-pin="'+s.code+'">☆</div></div></div><div class="mid"><span class="price">等候區</span></div></div></div>'); }); restoreLayout(); renderPins(); initSortable(); applyFocus(); setTimeout(function(){ autoFitAllMa(); initAllSkdj(); updateSectionCounts(); }, 250); window.addEventListener('resize', function(){ autoFitAllMa(); initAllSkdj(); }); })();


  }
  if(upBtn) upBtn.addEventListener('click', function(){ filterCards('up'); });
  if(downBtn) downBtn.addEventListener('click', function(){ filterCards('down'); });
  if(allBtn) allBtn.addEventListener('click', function(){ filterCards('all'); });
});


// V58 漲/跌篩選 帶數量 綠底紅底粉紫 無空格
document.addEventListener('DOMContentLoaded', function(){
  function updateCounts(){
    var up=0, down=0;
    document.querySelectorAll('.card').forEach(function(c){
      var pctEl = c.querySelector('.pct');
      if(!pctEl || pctEl.textContent.includes('限流')) return;
      if(pctEl.classList.contains('pct-up')) up++;
      else if(pctEl.classList.contains('pct-down')) down++;
      else {
        var t = pctEl.textContent;
        if(t.includes('+')) up++;
        else if(t.includes('-')) down++;
      }
    });
    var upBtn = document.getElementById('filterUpBtn');
    var downBtn = document.getElementById('filterDownBtn');
    if(upBtn) upBtn.textContent = '漲'+up+'隻';
    if(downBtn) downBtn.textContent = '跌'+down+'隻';
  }
  setTimeout(updateCounts, 1500);
  setInterval(updateCounts, 5000);
  function filterCards(type){
    document.querySelectorAll('.card').forEach(function(c){
      var pctEl = c.querySelector('.pct');
      if(!pctEl){ c.style.display=''; return; }
      var isUp = pctEl.classList.contains('pct-up');
      var isDown = pctEl.classList.contains('pct-down');
      if(!isUp && !isDown){
        var txt = pctEl.textContent;
        if(txt.includes('+')) isUp=true;
        else if(txt.includes('-')) isDown=true;
      }
      if(type==='up') c.style.display = isUp ? '' : 'none';
      else if(type==='down') c.style.display = isDown ? '' : 'none';
      else c.style.display = '';
    });
  }
  var upBtn = document.getElementById('filterUpBtn');
  var downBtn = document.getElementById('filterDownBtn');
  var allBtn = document.getElementById('filterAllBtn');
  if(upBtn) upBtn.addEventListener('click', function(){ filterCards('up'); });
  if(downBtn) downBtn.addEventListener('click', function(){ filterCards('down'); });
  if(allBtn) allBtn.addEventListener('click', function(){ filterCards('all'); });
});

</script>
</body></html>
"""

html_final = html_template.replace("__UPDATE_TIME__", hk_now).replace("__COUNT__", str(len(results))).replace("__CARDS__", cards)

with open("docs/index.html","w",encoding="utf-8") as f:
    f.write(html_final)

print(f"V35 時K包含盤前後 CCI全顯示 月亮 白色火箭 黑色匯出")
