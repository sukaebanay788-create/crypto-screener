import streamlit as st
import ccxt
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Crypto Screener")

st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; padding-left: 0rem; padding-right: 0rem; }
    div[data-testid="column"] { padding: 0px !important; }
    .stPlotlyChart { margin: 0px; padding: 0px; }
    .coin-list-item { font-size: 14px; padding: 4px 8px; cursor: pointer; border-bottom: 1px solid #333; }
    .coin-list-item:hover { background-color: #2c3e50; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_exchange():
    # Пытаемся подключиться к OKX, Bybit, Bitget (можно менять)
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
    # Если ни одна не работает
    st.error("Не удалось подключиться к OKX, Bybit и Bitget. Попробуйте позже.")
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
    result = popular + [p for p in usdt_pairs if p not in popular][:35]
    return result

@st.cache_data(ttl=60)
def fetch_ohlcv(symbol, timeframe='1h', limit=200):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame()

if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = 'BTC/USDT'

symbols = get_usdt_symbols()
if not symbols:
    st.stop()

left_col, right_col = st.columns([5, 1], gap="small")

with left_col:
    st.header(f"{st.session_state.selected_symbol} – 1H", anchor=False)
    df = fetch_ohlcv(st.session_state.selected_symbol, timeframe='1h', limit=200)
    if not df.empty:
        fig = go.Figure(data=[go.Candlestick(
            x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
            name='OHLC', increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
        )])
        fig.update_layout(
            height=700, margin=dict(l=10, r=10, t=30, b=10),
            xaxis_rangeslider_visible=False, template='plotly_dark',
            showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#333'),
            paper_bgcolor='#0e1117', plot_bgcolor='#0e1117'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.warning("Нет данных для отображения")

with right_col:
    st.markdown("**📋 Все монеты (USDT)**")
    search = st.text_input("🔍 Поиск", placeholder="BTC, ETH...", label_visibility="collapsed")
    filtered_symbols = symbols if not search else [s for s in symbols if search.upper() in s]
    with st.container(height=650):
        for sym in filtered_symbols:
            if st.button(sym, key=f"btn_{sym}", use_container_width=True,
                         type="secondary" if sym != st.session_state.selected_symbol else "primary"):
                st.session_state.selected_symbol = sym
                st.rerun()
