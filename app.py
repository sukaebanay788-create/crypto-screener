import streamlit as st
import ccxt
import pandas as pd
import time
import json

st.set_page_config(layout="wide", page_title="Screener", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { padding: 0.5rem 1rem; max-width: 100%; }
    div[data-testid="column"] { padding: 0px !important; }
    .element-container { margin-bottom: 0px !important; }
    button[kind="secondary"], button[kind="primary"] {
        border-radius: 3px; font-size: 11px; padding: 2px 6px; margin: 0; min-height: 28px;
    }
    #MainMenu, header, footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_exchange():
    for name in ['bybit', 'okx', 'bitget', 'binance']:
        try:
            if name == 'binance':
                ex = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
            elif name == 'okx':
                ex = ccxt.okx({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
            elif name == 'bybit':
                ex = ccxt.bybit({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
            elif name == 'bitget':
                ex = ccxt.bitget({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
            ex.load_markets()
            return ex
        except Exception:
            continue
    st.error("No exchange available")
    st.stop()

ex = get_exchange()
exchange_name = ex.id.upper()

@st.cache_data(ttl=120)
def get_symbols():
    markets = ex.load_markets()
    return [s for s in markets if s.endswith('/USDT') and markets[s]['active']
            and markets[s].get('spot', True)]

@st.cache_data(ttl=20)
def get_screener_data(symbols):
    data = []
    try:
        for i in range(0, min(len(symbols), 80), 50):
            chunk = symbols[i:i+50]
            tickers = ex.fetch_tickers(chunk)
            for sym in chunk:
                ticker = tickers.get(sym, {})
                price = ticker.get('last', 0) or 0
                change24 = ticker.get('percentage', 0) or 0
                
                change5 = 0
                change15 = 0
                try:
                    c5 = ex.fetch_ohlcv(sym, '5m', limit=3)
                    if len(c5) >= 2:
                        change5 = ((c5[-1][4] - c5[0][4]) / c5[0][4]) * 100
                except: pass
                    
                try:
                    c15 = ex.fetch_ohlcv(sym, '15m', limit=3)
                    if len(c15) >= 2:
                        change15 = ((c15[-1][4] - c15[0][4]) / c15[0][4]) * 100
                except: pass
                
                data.append({'symbol': sym, 'price': price, 'change24': change24,
                            'change5': change5, 'change15': change15})
    except: pass
    return data

def get_chart_data(symbol, timeframe):
    limit = 1000
    candles = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
    if not candles:
        return []
    return candles

# ── State ──
if 'coin' not in st.session_state:
    st.session_state.coin = 'BTC/USDT'
if 'tf' not in st.session_state:
    st.session_state.tf = '1h'
if 'sort' not in st.session_state:
    st.session_state.sort = 'change5'
if 'search' not in st.session_state:
    st.session_state.search = ''
if 'last_fetch' not in st.session_state:
    st.session_state.last_fetch = 0

symbols = get_symbols()
screen_data = get_screener_data(symbols)

# ── Layout ──
chart_area, sidebar = st.columns([5, 1])

# ── CHART AREA ──
with chart_area:
    # Top bar
    tfs = ['1m', '5m', '30m', '4h']
    col_ex, col_tfs = st.columns([1, 3])
    with col_ex:
        st.markdown(f"`{exchange_name}`")
    cols = col_tfs.columns(len(tfs))
    for i, tf in enumerate(tfs):
        with cols[i]:
            active = tf == st.session_state.tf
            if st.button(tf, key=f"tf_{tf}",
                        type="primary" if active else "secondary",
                        use_container_width=True):
                st.session_state.tf = tf
                st.rerun()

    # TradingView Chart via HTML component
    chart_container = st.container()
    with chart_container:
        try:
            candles = get_chart_data(st.session_state.coin, st.session_state.tf)
            
            if candles:
                df = pd.DataFrame(candles, columns=['t','o','h','l','c','v'])
                current = df.iloc[-1]['c']
                prev = df.iloc[-2]['c'] if len(df) > 1 else current
                chg = ((current - prev) / prev) * 100
                color = "#00d084" if chg >= 0 else "#ff4757"
                
                # Prepare data for TradingView
                tv_data = []
                for _, row in df.iterrows():
                    tv_data.append({
                        'time': int(row['t'] / 1000),
                        'open': float(row['o']),
                        'high': float(row['h']),
                        'low': float(row['l']),
                        'close': float(row['c']),
                    })
                
                tv_json = json.dumps(tv_data)
                
                st.components.v1.html(f"""
                <script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
                <div id="chart" style="width:100%;height:720px;background:#0a0a0a;"></div>
                <script>
                const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
                    width: document.getElementById('chart').clientWidth,
                    height: 720,
                    layout: {{
                        background: {{type: 'solid', color: '#0a0a0a'}},
                        textColor: '#888',
                    }},
                    grid: {{
                        vertLines: {{color: '#1a1a1a'}},
                        horzLines: {{color: '#1a1a1a'}},
                    }},
                    crosshair: {{
                        mode: LightweightCharts.CrosshairMode.Normal,
                    }},
                    rightPriceScale: {{
                        borderColor: '#1a1a1a',
                    }},
                    timeScale: {{
                        borderColor: '#1a1a1a',
                        timeVisible: true,
                        secondsVisible: false,
                    }},
                    handleScroll: {{
                        mouseWheel: true,
                        pressedMouseMove: true,
                    }},
                    handleScale: {{
                        axisPressedMouseMove: true,
                        mouseWheel: true,
                        pinch: true,
                    }},
                }});
                
                const candlestickSeries = chart.addCandlestickSeries({{
                    upColor: '#00d084',
                    downColor: '#ff4757',
                    borderUpColor: '#00d084',
                    borderDownColor: '#ff4757',
                    wickUpColor: '#00d084',
                    wickDownColor: '#ff4757',
                }});
                
                candlestickSeries.setData({tv_data});
                
                chart.timeScale().fitContent();
                
                window.addEventListener('resize', () => {{
                    chart.applyOptions({{ width: document.getElementById('chart').clientWidth }});
                }});
                </script>
                """, height=720)
                
                # Price display
                st.markdown(
                    f"`{current:.6f}`  "
                    f"<span style='color:{color};font-weight:bold;font-size:18px'>{chg:+.2f}%</span>",
                    unsafe_allow_html=True
                )
        except Exception as e:
            st.warning(str(e))

    # Auto-refresh
    now = time.time()
    if now - st.session_state.last_fetch > 5:
        st.session_state.last_fetch = now
        time.sleep(0.5)
        st.rerun()

# ── SIDEBAR ──
with sidebar:
    s1, s2, s3 = st.columns(3)
    with s1:
        if st.button("5m", type="primary" if st.session_state.sort == 'change5' else "secondary",
                    use_container_width=True):
            st.session_state.sort = 'change5'
            st.rerun()
    with s2:
        if st.button("15m", type="primary" if st.session_state.sort == 'change15' else "secondary",
                    use_container_width=True):
            st.session_state.sort = 'change15'
            st.rerun()
    with s3:
        if st.button("24h", type="primary" if st.session_state.sort == 'change24' else "secondary",
                    use_container_width=True):
            st.session_state.sort = 'change24'
            st.rerun()
    
    search_val = st.text_input("", key="search_input", label_visibility="collapsed",
                               placeholder="BTC...")
    
    screen_data.sort(key=lambda x: x[st.session_state.sort], reverse=True)
    
    filtered = screen_data
    if search_val:
        s = search_val.upper()
        filtered = [x for x in screen_data if s in x['symbol'].replace('/USDT', '')]
    
    with st.container(height=550):
        for item in filtered[:40]:
            sym = item['symbol']
            name = sym.replace('/USDT', '')
            
            if st.session_state.sort == 'change5':
                chg = item['change5']
            elif st.session_state.sort == 'change15':
                chg = item['change15']
            else:
                chg = item['change24']
            
            active = "primary" if sym == st.session_state.coin else "secondary"
            sign = "+" if chg >= 0 else ""
            
            if st.button(f"{name}  {sign}{chg:.1f}%",
                        key=f"coin_{sym}",
                        type=active,
                        use_container_width=True):
                st.session_state.coin = sym
                st.rerun()
