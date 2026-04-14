import streamlit as st
import pandas as pd
from pycoingecko import CoinGeckoAPI
import plotly.graph_objects as go
from binance.client import Client

# ------------------ НАСТРОЙКА СТРАНИЦЫ ------------------
st.set_page_config(layout="wide")

# ------------------ ИНИЦИАЛИЗАЦИЯ API ------------------
cg = CoinGeckoAPI()
binance_client = Client()  # Публичный клиент Binance (без ключей)

# ------------------ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ------------------
@st.cache_data(ttl=60)
def load_coins_list():
    """Список топ-100 монет с CoinGecko (сортировка по росту за 24ч)"""
    data = cg.get_coins_markets(vs_currency='usd', order='market_cap_desc', per_page=100, page=1)
    df = pd.DataFrame(data)
    df = df[['id', 'symbol', 'name', 'current_price', 'price_change_percentage_24h']]
    df = df.sort_values(by='price_change_percentage_24h', ascending=False)
    return df

@st.cache_data(ttl=300)
def load_binance_klines(symbol, interval, limit=500):
    """Загружает свечные данные с Binance."""
    try:
        klines = binance_client.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit
        )
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['close'] = df['close'].astype(float)
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки данных Binance: {e}")
        return pd.DataFrame()

# ------------------ ЗАГРУЗКА СПИСКА МОНЕТ ------------------
df_coins = load_coins_list()

# ------------------ ИНТЕРФЕЙС: ДВЕ КОЛОНКИ ------------------
col_chart, col_list = st.columns([5, 1.2])  # график широкий

# ------------------ ПРАВАЯ КОЛОНКА (СПИСОК) ------------------
with col_list:
    st.markdown("### 🔥 Рост за 24ч")

    event = st.dataframe(
        df_coins[['symbol', 'price_change_percentage_24h']],
        column_config={
            "symbol": "Монета",
            "price_change_percentage_24h": st.column_config.NumberColumn(
                "Рост %",
                format="%.2f %%"
            )
        },
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # По умолчанию BTC
    selected_coin_id = 'bitcoin'
    selected_symbol = 'BTC'

    if event.selection.rows:
        idx = event.selection.rows[0]
        selected_coin_id = df_coins.iloc[idx]['id']
        selected_symbol = df_coins.iloc[idx]['symbol'].upper()

# ------------------ ЛЕВАЯ КОЛОНКА (ГРАФИК) ------------------
with col_chart:
    # Заголовок и выбор таймфрейма в одной строке
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.markdown(f"### {selected_symbol}/USDT")
    with header_col2:
        timeframe = st.selectbox(
            "Таймфрейм",
            options=['1m', '5m', '30m', '4h'],
            index=1  # по умолчанию 5m
        )

    # Загружаем данные с Binance
    binance_symbol = f"{selected_symbol}USDT"
    df_chart = load_binance_klines(binance_symbol, interval=timeframe, limit=500)

    if not df_chart.empty:
        # Создаём ОДНУ панель с ценой и EMA
        fig = go.Figure()

        # Японские свечи
        fig.add_trace(
            go.Candlestick(
                x=df_chart['timestamp'],
                open=df_chart['open'],
                high=df_chart['high'],
                low=df_chart['low'],
                close=df_chart['close'],
                name='Цена',
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350',
                showlegend=True
            )
        )

        # EMA 65
        df_chart['EMA_65'] = df_chart['close'].ewm(span=65, adjust=False).mean()
        fig.add_trace(
            go.Scatter(
                x=df_chart['timestamp'],
                y=df_chart['EMA_65'],
                name='EMA 65',
                line=dict(color='#FFA500', width=2)  # оранжевый
            )
        )

        # EMA 125
        df_chart['EMA_125'] = df_chart['close'].ewm(span=125, adjust=False).mean()
        fig.add_trace(
            go.Scatter(
                x=df_chart['timestamp'],
                y=df_chart['EMA_125'],
                name='EMA 125',
                line=dict(color='#00BFFF', width=2)  # глубокий небесно-голубой
            )
        )

        # EMA 450
        df_chart['EMA_450'] = df_chart['close'].ewm(span=450, adjust=False).mean()
        fig.add_trace(
            go.Scatter(
                x=df_chart['timestamp'],
                y=df_chart['EMA_450'],
                name='EMA 450',
                line=dict(color='#FF69B4', width=2)  # ярко-розовый
            )
        )

        # ---------- ОФОРМЛЕНИЕ ----------
        fig.update_layout(
            template="plotly_dark",
            height=900,                     # большой график
            margin=dict(l=20, r=20, t=40, b=20),
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            xaxis_rangeslider_visible=False  # убираем слайдер снизу для чистоты
        )
        fig.update_xaxes(title_text="Время")
        fig.update_yaxes(title_text="Цена (USDT)")

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Не удалось загрузить данные для этого символа. Попробуйте другую монету.")
