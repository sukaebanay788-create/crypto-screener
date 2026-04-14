import streamlit as st
import ccxt
import pandas as pd
import plotly.graph_objects as go

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
    result = popular + [p for p in usdt_pairs if p not in popular][:35]
    return result

def fetch_ohlcv_raw(symbol, timeframe, limit, since=None):
    """Загружает сырые данные с биржи"""
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

# Инициализация сессии
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
if 'load_more' not in st.session_state:
    st.session_state.load_more = False

# Загружаем список монет
symbols = get_usdt_symbols()
if not symbols:
    st.stop()

# Проверяем, изменились ли монета или таймфрейм
need_reload = (st.session_state.selected_symbol != st.session_state.last_symbol or
               st.session_state.selected_tf != st.session_state.last_tf)

if need_reload:
    st.session_state.cached_df = pd.DataFrame()
    st.session_state.last_symbol = st.session_state.selected_symbol
    st.session_state.last_tf = st.session_state.selected_tf

# Основная загрузка данных
if st.session_state.cached_df.empty:
    # Первая загрузка — 200 свечей
    raw = fetch_ohlcv_raw(st.session_state.selected_symbol, st.session_state.selected_tf, limit=200)
    st.session_state.cached_df = ohlcv_to_df(raw)
else:
    # Проверяем, нужно ли догрузить историю
    if st.session_state.load_more and not st.session_state.cached_df.empty:
        oldest_ts = st.session_state.cached_df['timestamp'].min()
        # since должен быть в миллисекундах, берем самый старый timestamp минус 1 мс, чтобы не дублировать
        since = int(oldest_ts.timestamp() * 1000) - 1
        # Загружаем ещё 100 свечей до oldest_ts
        older_raw = fetch_ohlcv_raw(st.session_state.selected_symbol, st.session_state.selected_tf,
                                    limit=100, since=since)
        older_df = ohlcv_to_df(older_raw)
        if not older_df.empty:
            # Объединяем и удаляем дубликаты по timestamp
            combined = pd.concat([older_df, st.session_state.cached_df]).drop_duplicates('timestamp').sort_values('timestamp')
            st.session_state.cached_df = combined
        st.session_state.load_more = False

# Интерфейс
left_col, right_col = st.columns([5, 1], gap="small")

with left_col:
    col_title, col_tf = st.columns([3, 1])
    with col_title:
        st.header(f"{st.session_state.selected_symbol} – {st.session_state.selected_tf}", anchor=False)
    with col_tf:
        tf_options = ['1m', '5m', '30m', '4h', '1h']
        selected_tf = st.selectbox(
            "Таймфрейм",
            tf_options,
            index=tf_options.index(st.session_state.selected_tf) if st.session_state.selected_tf in tf_options else 4,
            label_visibility="collapsed"
        )
        if selected_tf != st.session_state.selected_tf:
            st.session_state.selected_tf = selected_tf
            st.rerun()

    df = st.session_state.cached_df

    if not df.empty:
        fig = go.Figure(data=[go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='OHLC',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350'
        )])

        fig.update_layout(
            height=700,
            margin=dict(l=10, r=10, t=30, b=10),
            xaxis_rangeslider_visible=False,
            dragmode='pan',
            template='plotly_dark',
            showlegend=False,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='#333'),
            paper_bgcolor='#0e1117',
            plot_bgcolor='#0e1117'
        )

        # Получаем данные о текущем отображении из plotly events
        chart_data = st.plotly_chart(
            fig,
            use_container_width=True,
            config={'scrollZoom': True, 'displayModeBar': False, 'doubleClick': 'reset'},
            key="candlestick_chart"
        )

        # Проверяем событие relayoutData
        if chart_data and 'xaxis.range[0]' in chart_data:
            left_bound = pd.to_datetime(chart_data['xaxis.range[0]'])
            min_ts = df['timestamp'].min()
            # Если пользователь приблизился к началу данных (разница меньше 10% от всего диапазона)
            total_range = (df['timestamp'].max() - min_ts).total_seconds()
            distance = (left_bound - min_ts).total_seconds()
            if total_range > 0 and distance < total_range * 0.1:
                st.session_state.load_more = True
                st.rerun()
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
