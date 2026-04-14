import streamlit as st
import ccxt
import pandas as pd
import plotly.graph_objects as go
import time

st.set_page_config(layout="wide", page_title="Screener", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { 
        padding: 0.5rem 1rem; 
        max-width: 100%;
    }
    .stPlotlyChart { margin: 0; padding: 0; }
    div[data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }
    div[data-testid="column"] { padding: 0px !important; }
    .element-container { margin-bottom: 0px !important; }
    button[kind="secondary"], button[kind="primary"] { 
        border-radius: 4px; 
        font-size: 13px;
        padding: 4px 8px;
        margin: 2px 0;
    }
    .css-1v0mbdj { border: none !important; }
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .coin-row { 
        display: flex; 
        justify-content: space-between; 
        padding: 6px 8px;
        cursor: pointer;
        border-bottom: 1px solid #1a1a1a;
        transition: background 0.1s;
    }
    .coin-row:hover { background: #1a2332; }
    .up { color: #00d084; }
    .down { color: #ff4757; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_exchange():
    ex = ccxt.okx({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    ex.load_markets()
    return ex

ex = get_exchange()

@st.cache_data(ttl=60)
def get_markets():
    markets = ex.load_markets()
    symbols = [s for s in markets.keys() 
               if s.endswith('/USDT') 
               and markets[s]['active']
               and not markets[s].get('spot', True) == False]
    return symbols

def get_price_change(symbol, timeframe, minutes):
    """Calculate price change % over last N minutes"""
    try:
        candles = ex.fetch_ohlcv(symbol, timeframe, limit=100)
        if not candles:
            return 0
        df = pd.DataFrame(candles, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        now = df.iloc[-1]['t']
        target = now - (minutes * 60 * 1000)
        before = df[df['t'] <= target]
        if before.empty:
            return 0
        old = before.iloc[-1]['c']
        new = df.iloc[-1]['c']
        return ((new - old) / old) * 100
    except:
        return 0

@st.cache_data(ttl=30)
def fetch_all_changes(symbols, timeframe='1h'):
    """Get 24h change + short-term changes"""
    data = []
    tickers = ex.fetch_tickers(symbols[:50])
    
    for sym in symbols[:50]:
        try:
            ticker = tickers.get(sym, {})
            change24 = ticker.get('percentage', 0) or 0
            price = ticker.get('last', 0) or 0
            vol = ticker.get('quoteVolume', 0) or 0
            
            # Calculate 5m and 15m changes
            try:
                candles5 = ex.fetch_ohlcv(sym, '5m', limit=20)
                change5 = 0
                if len(candles5) >= 2:
                    old5 = candles5[0][4]
                    new5 = candles5[-1][4]
                    change5 = ((new5 - old5) / old5) * 100
            except:
                change5 = 0
                
            try:
                candles15 = ex.fetch_ohlcv(sym, '15m', limit=20)
                change15 = 0
                if len(candles15) >= 2:
                    old15 = candles15[0][4]
                    new15 = candles15[-1][4]
                    change15 = ((new15 - old15) / old15) * 100
            except:
                change15 = 0
            
            data.append({
                'symbol': sym,
                'price': price,
                'change24': change24,
                'change5': change5,
                'change15': change15,
                'volume': vol
            })
        except:
            continue
    
    return data

# State
if 'coin' not in st.session_state:
    st.session_state.coin = 'BTC/USDT'
if 'tf' not in st.session_state:
    st.session_state.tf = '1h'
if 'sort' not in st.session_state:
    st.session_state.sort = 'change5'
if 'search' not in st.session_state:
    st.session_state.search = ''

symbols = get_markets()

# Fetch screener data
screen_data = fetch_all_changes(symbols)

# Sort
reverse = True
if screen_data:
    screen_data.sort(key=lambda x: x[st.session_state.sort], reverse=reverse)

# Filter
filtered = screen_data
if st.session_state.search:
    s = st.session_state.search.upper()
    filtered = [x for x in screen_data if s in x['symbol'].replace('/USDT', '')]

# Main layout - chart takes most space
chart_area, sidebar = st.columns([5, 1])

with chart_area:
    # Top bar
    bar1, bar2, bar3 = st.columns([1, 2, 1])
    
    with bar1:
        st.markdown(f"## {st.session_state.coin.replace('/USDT', '')}")
    
    with bar2:
        # Timeframe selector
        tfs = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d']
        cols = st.columns(len(tfs))
        for i, tf in enumerate(tfs):
            with cols[i]:
                active = tf == st.session_state.tf
                if st.button(tf, key=f"tf_{tf}", 
                            type="primary" if active else "secondary",
                            use_container_width=True):
                    st.session_state.tf = tf
                    st.rerun()
    
    with bar3:
        pass
    
    # Chart
    try:
        candles = ex.fetch_ohlcv(st.session_state.coin, st.session_state.tf, limit=300)
        df = pd.DataFrame(candles, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        df['time'] = pd.to_datetime(df['t'], unit='ms')
        
        current = df.iloc[-1]['c']
        prev = df.iloc[-2]['c']
        is_up = current >= prev
        
        # Price display
        col_p1, col_p2 = st.columns([1, 3])
        with col_p1:
            st.markdown(f"### {current:.6f}")
        with col_p2:
            chg = ((current - prev) / prev) * 100
            color = "#00d084" if chg >= 0 else "#ff4757"
            st.markdown(f"### <span style='color:{color}'>{chg:+.2f}%</span>", 
                       unsafe_allow_html=True)
        
        # Candlestick chart
        fig = go.Figure(data=[go.Candlestick(
            x=df['time'],
            open=df['o'],
            high=df['h'],
            low=df['l'],
            close=df['c'],
            increasing=dict(line=dict(color='#00d084'), fillcolor='#00d084'),
            decreasing=dict(line=dict(color='#ff4757'), fillcolor='#ff4757')
        )])
        
        fig.update_layout(
            height=650,
            margin=dict(l=0, r=0, t=0, b=0, pad=0),
            xaxis=dict(
                rangeslider=dict(visible=False),
                showgrid=False,
                zeroline=False
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='#1a1a1a',
                side='right',
                zeroline=False
            ),
            plot_bgcolor='#0a0a0a',
            paper_bgcolor='#0a0a0a',
            dragmode='pan',
            showlegend=False
        )
        
        fig.update_xaxes(
            showline=False,
            tickfont=dict(size=10)
        )
        fig.update_yaxes(
            showline=False,
            tickfont=dict(size=10)
        )
        
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                'scrollZoom': True,
                'displayModeBar': False,
                'doubleClick': 'reset',
                'modeBarButtonsToRemove': ['lasso2d', 'select2d']
            }
        )
        
    except Exception as e:
        st.error(f"Error: {e}")

with sidebar:
    # Sort buttons
    st.markdown("### Sort")
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
    st.markdown("### Find")
    search_val = st.text_input("", key="search_input", label_visibility="collapsed", 
                               placeholder="BTC...")
    st.session_state.search = search_val
    
    # Coin list
    st.markdown("---")
    
    with st.container(height=500):
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
            color_class = "up" if chg >= 0 else "down"
            
            if st.button(f"{name}  {sign}{chg:.1f}%", 
                        key=f"coin_{sym}",
                        type=active,
                        use_container_width=True):
                st.session_state.coin = sym
                st.rerun()
