import streamlit as st
import ccxt
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="Crypto Screener")

st.markdown("""
<style>
    .block-container { padding-top: 0.5rem; padding-bottom: 0rem; padding-left: 0rem; padding-right: 0rem; }
    div[data-testid="column"] { padding: 0px !important; }
    .stPlotlyChart { margin: 0px; padding: 0px; }
    .coin-row { display: flex; align-items: center; padding: 6px 8px; cursor: pointer; border-bottom: 1px solid #1a1a2e; }
    .coin-row:hover { background-color: #1e2a3a; }
    .stButton>button { padding: 0.25rem 0.5rem; font-size: 12px; }
    div[data-testid="stVerticalBlock"] > div { margin: 0 !important; padding: 0 !important; }
    .sort-header { font-size: 11px; color: #888; padding: 4px 8px; cursor: pointer; user-select: none; }
    .sort-header:hover { color: #fff; }
    .sort-header.active { color: #26a69a; font-weight: bold; }
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_exchange():
    exchanges_to_try = [
        ccxt.okx({'enableRateLimit': True}),
        ccxt.bybit({'enableRateLimit': True}),
        ccxt.bitget({'enableRateLimit': True})
    ]
    for exchange in exchanges_to_try:
        try:
            exchange.load_markets()
            return exchange
        except Exception:
            continue
    st.error("Не удалось подключиться к OKX, Bybit и Bitget.")
    st.stop()

exchange = init_exchange()

@st.cache_data(ttl=300)
def get_usdt_symbols():
    try:
        markets = exchange.load_markets()
    except Exception as e:
        st.error(f"Ошибка загрузки рынков: {e}")
        return []
    usdt_pairs = [symbol for symbol in markets if symbol.endswith('/USDT')]
    popular = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
               'ADA/USDT', 'DOGE/USDT', 'MATIC/USDT', 'DOT/USDT', 'LTC/USDT',
               'AVAX/USDT', 'LINK/USDT', 'UNI/USDT', 'ATOM/USDT', 'ETC/USDT']
    result = popular + [p for p in usdt_pairs if p not in popular][:85]
    return result

@st.cache_data(ttl=60)
def fetch_tickers_for_symbols(symbols_list):
    try:
        all_tickers = {}
        chunk_size = 20
        for i in range(0, len(symbols_list), chunk_size):
            chunk = symbols_list[i:i+chunk_size]
            for sym in chunk:
                try:
                    ticker = exchange.fetch_ticker(sym)
                    all_tickers[sym] = ticker
                except Exception:
                    continue
        return all_tickers
    except Exception:
        return {}

def fetch_ohlcv_raw(symbol, timeframe, limit, since=None):
    try:
        if since:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        else:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return ohlcv
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return []

def ohlcv_to_df(ohlcv):
    if not ohlcv:
        return pd.DataFrame()
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calc_change_from_ohlcv(df, minutes):
    if df.empty or len(df) < 2:
        return 0.0
    target_ms = minutes * 60 * 1000
    now_ts = df['timestamp'].max()
    target_ts = now_ts - pd.Timedelta(milliseconds=target_ms)
    closest = df[df['timestamp'] <= target_ts]
    if closest.empty:
        oldest = df.iloc[0]
        newest = df.iloc[-1]
        return ((newest['close'] - oldest['close']) / oldest['close']) * 100
    old_price = closest.iloc[-1]['close']
    new_price = df.iloc[-1]['close']
    return ((new_price - old_price) / old_price) * 100

# Сессия
if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = 'BTC/USDT'
if 'selected_tf' not in st.session_state:
    st.session_state.selected_tf = '1h'
if 'cached_df' not in st.session_state:
    st.session_state.cached_df = pd.DataFrame()
if 'last_symbol' not in st.session_state:
    st.session_state.last_symbol = None
if 'last_tf' not in st.session_state:
    st.session_state.last_tf = None
if 'sort_by' not in st.session_state:
    st.session_state.sort_by = '24h'
if 'ticker_data' not in st.session_state:
    st.session_state.ticker_data = {}
if 'last_ticker_update' not in st.session_state:
    st.session_state.last_ticker_update = 0

symbols = get_usdt_symbols()
if not symbols:
    st.stop()

# Загрузка тикеров для расчёта изменений
import time
current_time = time.time()
if current_time - st.session_state.last_ticker_update > 60 or not st.session_state.ticker_data:
    st.session_state.ticker_data = fetch_tickers_for_symbols(symbols)
    st.session_state.last_ticker_update = current_time

ticker_data = st.session_state.ticker_data

# Собираем данные для сортировки
coins_data = []
for sym in symbols:
    ticker = ticker_data.get(sym, {})
    change_24h = ticker.get('percentage', 0.0) or 0.0
    
    # Для 5м и 15м берём последние OHLCV
    ohlcv_5m = fetch_ohlcv_raw(sym, '5m', 50)
    df_5m = ohlcv_to_df(ohlcv_5m)
    change_5m = calc_change_from_ohlcv(df_5m, 5) if not df_5m.empty else 0.0
    
    ohlcv_15m = fetch_ohlcv_raw(sym, '15m', 50)
    df_15m = ohlcv_to_df(ohlcv_15m)
    change_15m = calc_change_from_ohlcv(df_15m, 15) if not df_15m.empty else 0.0
    
    price = ticker.get('last', 0.0) or 0.0
    volume = ticker.get('quoteVolume', 0.0) or 0.0
    
    coins_data.append({
        'symbol': sym,
        'price': price,
        'change_24h': change_24h,
        'change_5m': change_5m,
        'change_15m': change_15m,
        'volume': volume
    })

# Сортировка
sort_key = st.session_state.sort_by
if sort_key == '5m':
    coins_data.sort(key=lambda x: x['change_5m'], reverse=True)
elif sort_key == '15m':
    coins_data.sort(key=lambda x: x['change_15m'], reverse=True)
else:
    coins_data.sort(key=lambda x: x['change_24h'], reverse=True)

# Проверка на смену монеты/таймфрейма
need_reload = (st.session_state.selected_symbol != st.session_state.last_symbol or
               st.session_state.selected_tf != st.session_state.last_tf)
if need_reload:
    st.session_state.cached_df = pd.DataFrame()
    st.session_state.last_symbol = st.session_state.selected_symbol
    st.session_state.last_tf = st.session_state.selected_tf

if st.session_state.cached_df.empty:
    raw = fetch_ohlcv_raw(st.session_state.selected_symbol, st.session_state.selected_tf, limit=200)
    st.session_state.cached_df = ohlcv_to_df(raw)

# Основной лейаут - без отступов
chart_col, list_col = st.columns([4, 1], gap="small")

with chart_col:
    # Хедер
    hdr = st.container()
    with hdr:
        col_title, col_tf = st.columns([4, 1])
        with col_title:
            st.markdown(f"### {st.session_state.selected_symbol}", unsafe_allow_html=True)
        with col_tf:
            tf_options = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
            selected_tf = st.selectbox(
                "",
                tf_options,
                index=tf_options.index(st.session_state.selected_tf) if st.session_state.selected_tf in tf_options else 4,
                label_visibility="collapsed"
            )
            if selected_tf != st.session_state.selected_tf:
                st.session_state.selected_tf = selected_tf
                st.rerun()
    
    # График
    df = st.session_state.cached_df
    
    if not df.empty:
        last_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        price_up = last_price >= prev_price
        
        st.markdown(f"### {last_price:.4f} {'🟢' if price_up else '🔴'}", unsafe_allow_html=True)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='OHLC',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
            increasing_fillcolor='#26a69a',
            decreasing_fillcolor='#ef5350'
        )])
        
        fig.update_layout(
            height=600,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis_rangeslider_visible=False,
            dragmode='pan',
            template='plotly_dark',
            showlegend=False,
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=True, gridcolor='#1a1a2e', side='right', zeroline=False),
            paper_bgcolor='#0e1117',
            plot_bgcolor='#0e1117'
        )
        
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={'scrollZoom': True, 'displayModeBar': False, 'doubleClick': 'reset'}
        )
        
        # Загрузить ещё
        if st.button("← Загрузить ещё", use_container_width=False):
            oldest_ts = df['timestamp'].min()
            since = int(oldest_ts.timestamp() * 1000) - 1
            older_raw = fetch_ohlcv_raw(st.session_state.selected_symbol, st.session_state.selected_tf,
                                        limit=100, since=since)
            older_df = ohlcv_to_df(older_raw)
            if not older_df.empty:
                combined = pd.concat([older_df, df]).drop_duplicates('timestamp').sort_values('timestamp')
                st.session_state.cached_df = combined
                st.rerun()
    else:
        st.warning("Нет данных")

with list_col:
    # Сортировка
    st.markdown("**Сортировка:**", unsafe_allow_html=True)
    sort_cols = st.columns(3)
    with sort_cols[0]:
        if st.button("5м", use_container_width=True, 
                     type="primary" if st.session_state.sort_by == '5m' else "secondary"):
            st.session_state.sort_by = '5m'
            st.rerun()
    with sort_cols[1]:
        if st.button("15м", use_container_width=True,
                     type="primary" if st.session_state.sort_by == '15m' else "secondary"):
            st.session_state.sort_by = '15m'
            st.rerun()
    with sort_cols[2]:
        if st.button("24ч", use_container_width=True,
                     type="primary" if st.session_state.sort_by == '24h' else "secondary"):
            st.session_state.sort_by = '24h'
            st.rerun()
    
    # Поиск
    search = st.text_input("", placeholder="🔍 BTC...", label_visibility="collapsed")
    
    # Список монет
    filtered = coins_data
    if search:
        s = search.upper()
        filtered = [c for c in coins_data if s in c['symbol']]
    
    with st.container(height=600):
        for coin in filtered:
            sym = coin['symbol']
            change_val = coin[f'change_{st.session_state.sort_by.replace("24h", "24h")}']
            if st.session_state.sort_by == '24h':
                change_val = coin['change_24h']
            elif st.session_state.sort_by == '5m':
                change_val = coin['change_5m']
            else:
                change_val = coin['change_15m']
            
            is_selected = sym == st.session_state.selected_symbol
            change_color = '#26a69a' if change_val >= 0 else '#ef5350'
            change_sign = '+' if change_val >= 0 else ''
            
            btn_type = "primary" if is_selected else "secondary"
            
            if st.button(
                f"{sym.replace('/USDT', '')}  {change_sign}{change_val:.1f}%",
                key=f"btn_{sym}",
                use_container_width=True,
                type=btn_type
            ):
                st.session_state.selected_symbol = sym
                st.rerun()
