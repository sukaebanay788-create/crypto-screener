import streamlit as st
import ccxt
import pandas as pd
import plotly.graph_objects as go
import time

st.set_page_config(layout="wide", page_title="Screener", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { padding: 0.5rem 1rem; max-width: 100%; }
    .stPlotlyChart { margin: 0; padding: 0; }
    div[data-testid="column"] { padding: 0px !important; }
    .element-container { margin-bottom: 0px !important; }
    button[kind="secondary"], button[kind="primary"] {
        border-radius: 3px; font-size: 11px; padding: 2px 6px; margin: 0; min-height: 28px;
    }
    #MainMenu, header, footer {visibility: hidden;}
    .up { color: #00d084; }
    .down { color: #ff4757; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_exchange():
    ex = ccxt.okx({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
    ex.load_markets()
    return ex

ex = get_exchange()

@st.cache_data(ttl=120)
def get_symbols():
    markets = ex.load_markets()
    return [s for s in markets if s.endswith('/USDT') and markets[s]['active']]

@st.cache_data(ttl=20)
def get_screener_data(symbols):
    """Fetch screener data — cached for 20 sec"""
    data = []
    try:
        tickers = ex.fetch_tickers(symbols[:60])
        for sym in symbols[:60]:
            ticker = tickers.get(sym, {})
            price = ticker.get('last', 0) or 0
            change24 = ticker.get('percentage', 0) or 0
            volume = ticker.get('quoteVolume', 0) or 0
            
            # 5m change
            try:
                c5 = ex.fetch_ohlcv(sym, '5m', limit=12)
                change5 = 0
                if len(c5) >= 2:
                    change5 = ((c5[-1][4] - c5[0][4]) / c5[0][4]) * 100
            except:
                change5 = 0
                
            # 15m change
            try:
                c15 = ex.fetch_ohlcv(sym, '15m', limit=12)
                change15 = 0
                if len(c15) >= 2:
                    change15 = ((c15[-1][4] - c15[0][4]) / c15[0][4]) * 100
            except:
                change15 = 0
            
            data.append({'symbol': sym, 'price': price, 'change24': change24,
                        'change5': change5, 'change15': change15, 'volume': volume})
    except:
        pass
    return data

@st.cache_data(ttl=5)
def get_chart_data(symbol, timeframe, limit=1000):
    """Fetch chart data — maximum candles (100 per request, multiple requests)"""
    all_candles = []
    since = None
    # Fetch up to 10 batches = 1000 candles
    for _ in range(10):
        try:
            candles = ex.fetch_ohlcv(symbol, timeframe, limit=100, since=since)
            if not candles:
                break
            all_candles = candles + all_candles
            if len(candles) < 100:
                break
            since = candles[0][0] - 1
            if len(all_candles) >= limit:
                break
        except:
            break
    df = pd.DataFrame(all_candles[-limit:], columns=['t', 'o', 'h', 'l', 'c', 'v'])
    df['time'] = pd.to_datetime(df['t'], unit='ms')
    return df

# ── State ──
if 'coin' not in st.session_state:
    st.session_state.coin = 'BTC/USDT'
if 'tf' not in st.session_state:
    st.session_state.tf = '1h'
if 'sort' not in st.session_state:
    st.session_state.sort = 'change5'
if 'search' not in st.session_state:
    st.session_state.search = ''
if 'last_update' not in st.session_state:
    st.session_state.last_update = 0

symbols = get_symbols()

# ── Layout ──
chart_area, sidebar = st.columns([5, 1])

with chart_area:
    # TF bar only
    tfs = ['1m', '5m', '30m', '4h']
    cols = st.columns(len(tfs))
    for i, tf in enumerate(tfs):
        with cols[i]:
            active = tf == st.session_state.tf
            if st.button(tf, key=f"tf_{tf}",
                        type="primary" if active else "secondary",
                        use_container_width=True):
                st.session_state.tf = tf
                st.rerun()

    # Chart — full height
    try:
        df = get_chart_data(st.session_state.coin, st.session_state.tf)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df['time'], open=df['o'], high=df['h'], low=df['l'], close=df['c'],
            increasing=dict(line=dict(color='#00d084'), fillcolor='#00d084'),
            decreasing=dict(line=dict(color='#ff4757'), fillcolor='#ff4757')
        )])
        
        fig.update_layout(
            height=750,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(rangeslider=dict(visible=False), showgrid=False, zeroline=False),
            yaxis=dict(showgrid=True, gridcolor='#1a1a1a', side='right', zeroline=False),
            plot_bgcolor='#0a0a0a', paper_bgcolor='#0a0a0a',
            dragmode='pan', showlegend=False
        )
        fig.update_xaxes(showline=False, tickfont=dict(size=10))
        fig.update_yaxes(showline=False, tickfont=dict(size=10))
        
        st.plotly_chart(fig, use_container_width=True, config={
            'scrollZoom': True, 'displayModeBar': False,
            'doubleClick': 'reset', 'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        })
        
    except Exception as e:
        st.warning(f"No data: {e}")

with sidebar:
    # Sort buttons
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
    
    # Search
    search_val = st.text_input("", key="search_input", label_visibility="collapsed",
                               placeholder="BTC...")
    
    # Auto-refresh timer
    now = time.time()
    if now - st.session_state.last_update > 20:
        st.session_state.last_update = now
    
    # Get cached screener data
    screen_data = get_screener_data(symbols)
    
    # Sort
    screen_data.sort(key=lambda x: x[st.session_state.sort], reverse=True)
    
    # Filter
    filtered = screen_data
    if search_val:
        s = search_val.upper()
        filtered = [x for x in screen_data if s in x['symbol'].replace('/USDT', '')]
    
    # List
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
