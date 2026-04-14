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
    ex = ccxt.okx({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
    ex.load_markets()
    return ex

ex = get_exchange()
exchange_name = ex.id.upper()

@st.cache_data(ttl=120)
def get_symbols():
    markets = ex.load_markets()
    return [s for s in markets if s.endswith('/USDT') and markets[s]['active']
            and markets[s].get('spot', True)]

@st.cache_data(ttl=30)
def get_screener_data():
    """CoinGecko — все монеты за ОДИН запрос, супер быстро!"""
    import requests
    try:
        resp = requests.get(
            'https://api.coingecko.com/api/v3/coins/markets',
            params={
                'vs_currency': 'usd',
                'category': 'layer-1',
                'order': 'volume_desc',
                'per_page': 50,
                'price_change_percentage': '5m,15m,24h'
            },
            timeout=10
        )
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        result = []
        for coin in data:
            sym = coin['symbol'].upper()
            if not sym.endswith('USDT'):
                sym = sym + '/USDT'
            
            # Проверяем что символ есть на бирже
            if sym not in ex.markets:
                continue
            
            result.append({
                'symbol': sym,
                'price': coin.get('current_price', 0) or 0,
                '24h': coin.get('price_change_percentage_24h', 0) or 0,
                '5m': coin.get('price_change_percentage_5m', 0) or 0,
                '15m': coin.get('price_change_percentage_15m', 0) or 0,
                'volume': coin.get('total_volume', 0) or 0
            })
        return result
    except:
        return []

def get_chart_data(symbol, timeframe, limit=1000):
    """OKX pagination — 100 candles per request, up to 1000"""
    tf_ms = {'1m':60000,'5m':300000,'30m':1800000,'4h':14400000,
             '1h':3600000,'2h':7200000,'12h':43200000,'1d':86400000}
    candle_ms = tf_ms.get(timeframe, 3600000)
    
    candles = ex.fetch_ohlcv(symbol, timeframe, limit=100)
    if not candles:
        return []
    
    all_candles = candles[:]
    for _ in range(9):
        time.sleep(0.1)
        oldest_ts = all_candles[0][0]
        since = oldest_ts - (100 * candle_ms)
        older = ex.fetch_ohlcv(symbol, timeframe, limit=100, since=since)
        if not older or len(older) == 0:
            break
        older = [c for c in older if c[0] < oldest_ts]
        if not older:
            break
        all_candles = older + all_candles
        if len(all_candles) >= limit:
            break
    
    return all_candles

# ── State ──
if 'coin' not in st.session_state:
    st.session_state.coin = 'BTC/USDT'
if 'tf' not in st.session_state:
    st.session_state.tf = '1h'
if 'sort' not in st.session_state:
    st.session_state.sort = '24h'
if 'search' not in st.session_state:
    st.session_state.search = ''
if 'last_fetch' not in st.session_state:
    st.session_state.last_fetch = 0
if 'chart_limit' not in st.session_state:
    st.session_state.chart_limit = 1000

symbols = get_symbols()
screen_data = get_screener_data()

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
            candles = get_chart_data(st.session_state.coin, st.session_state.tf, 
                                     limit=st.session_state.chart_limit)

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

                # Price + load more button
                col_price, col_load = st.columns([1, 3])
                with col_price:
                    st.markdown(
                        f"`{current:.6f}`  "
                        f"<span style='color:{color};font-weight:bold;font-size:18px'>{chg:+.2f}%</span>",
                        unsafe_allow_html=True
                    )
                with col_load:
                    if st.button("⬇ Load more history"):
                        st.session_state.chart_limit = min(st.session_state.chart_limit + 1000, 5000)
                        st.rerun()
                    
                    st.caption(f"Loaded: {len(candles)} candles")
        except Exception as e:
            st.warning(str(e))

# ── SIDEBAR ──
with sidebar:
    # Sort buttons
    s1, s2, s3 = st.columns(3)
    with s1:
        if st.button("5m", type="primary" if st.session_state.sort == '5m' else "secondary",
                    use_container_width=True):
            st.session_state.sort = '5m'
            st.rerun()
    with s2:
        if st.button("15m", type="primary" if st.session_state.sort == '15m' else "secondary",
                    use_container_width=True):
            st.session_state.sort = '15m'
            st.rerun()
    with s3:
        if st.button("24h", type="primary" if st.session_state.sort == '24h' else "secondary",
                    use_container_width=True):
            st.session_state.sort = '24h'
            st.rerun()
    
    search_val = st.text_input("", key="search_input", label_visibility="collapsed",
                               placeholder="BTC...")
    
    screen_data.sort(key=lambda x: x[st.session_state.sort] or 0, reverse=True)
    
    filtered = screen_data
    if search_val:
        s = search_val.upper()
        filtered = [x for x in screen_data if s in x['symbol'].replace('/USDT', '')]
    
    with st.container(height=600):
        for item in filtered[:40]:
            sym = item['symbol']
            name = sym.replace('/USDT', '')
            chg = item[st.session_state.sort] or 0
            
            active = "primary" if sym == st.session_state.coin else "secondary"
            sign = "+" if chg >= 0 else ""
            
            if st.button(f"{name}  {sign}{chg:.1f}%",
                        key=f"coin_{sym}",
                        type=active,
                        use_container_width=True):
                st.session_state.coin = sym
                st.rerun()
