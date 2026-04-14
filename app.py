import streamlit as st
import ccxt
import time

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

# ── State ──
if 'coin' not in st.session_state:
    st.session_state.coin = 'BTC/USDT'
if 'tf' not in st.session_state:
    st.session_state.tf = '1h'
if 'sort' not in st.session_state:
    st.session_state.sort = '24h'
if 'search' not in st.session_state:
    st.session_state.search = ''

screen_data = get_screener_data()

# ── Layout ──
chart_area, sidebar = st.columns([5, 1])

# ── CHART AREA ──
with chart_area:
    # Top bar
    tfs = ['1m', '5m', '30m', '4h']
    col_ex, col_tfs = st.columns([1, 3])
    with col_ex:
        st.markdown("`Binance`")
    cols = col_tfs.columns(len(tfs))
    for i, tf in enumerate(tfs):
        with cols[i]:
            active = tf == st.session_state.tf
            if st.button(tf, key=f"tf_{tf}",
                        type="primary" if active else "secondary",
                        use_container_width=True):
                st.session_state.tf = tf
                st.rerun()

    # Chart with TradingView Lightweight Charts + Binance API
    chart_container = st.container()
    with chart_container:
        pair = st.session_state.coin.replace('/', '')
        tf_map = {'1m': '1m', '5m': '5m', '30m': '30m', '4h': '4h'}
        interval = tf_map.get(st.session_state.tf, '1h')
        
        st.components.v1.html(f"""
        <div id="chart" style="width:100%;height:720px;background:#0a0a0a;"></div>
        <script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
        <script>
        async function loadData() {{
            const resp = await fetch('https://api.binance.com/api/v3/klines?symbol={pair}&interval={interval}&limit=1000');
            const data = await resp.json();
            
            const candles = data.map(k => ({{
                time: Math.floor(k[0] / 1000),
                open: parseFloat(k[1]),
                high: parseFloat(k[2]),
                low: parseFloat(k[3]),
                close: parseFloat(k[4])
            }}));
            
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
                rightPriceScale: {{borderColor: '#1a1a1a'}},
                timeScale: {{borderColor: '#1a1a1a', timeVisible: true}},
                handleScroll: {{mouseWheel: true, pressedMouseMove: true}},
            }});
            
            const series = chart.addCandlestickSeries({{
                upColor: '#00d084',
                downColor: '#ff4757',
                borderUpColor: '#00d084',
                borderDownColor: '#ff4757',
                wickUpColor: '#00d084',
                wickDownColor: '#ff4757',
            }});
            
            series.setData(candles);
            chart.timeScale().fitContent();
        }}
        
        loadData();
        window.addEventListener('resize', () => {{
            const chartEl = document.getElementById('chart');
            if (chartEl) chartEl.style.width = '100%';
        }});
        </script>
        """, height=720)

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
    
    search_val = st.text_input("Search", key="search_input", 
                               placeholder="BTC...", label_visibility="collapsed")
    
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
