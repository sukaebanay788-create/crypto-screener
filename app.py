import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from pycoingecko import CoinGeckoAPI
from datetime import datetime

# ------------------ НАСТРОЙКА СТРАНИЦЫ ------------------
st.set_page_config(layout="wide", page_title="Крипто-скринер")

# ------------------ ИНИЦИАЛИЗАЦИЯ API ------------------
cg = CoinGeckoAPI()

# Публичный эндпоинт Binance (работает без ключей)
BINANCE_API_URL = "https://api.binance.com/api/v3"

# ------------------ ФУНКЦИИ ------------------
@st.cache_data(ttl=60)
def load_coins_list():
    """Список топ-100 монет с CoinGecko (сортировка по росту за 24ч)"""
    try:
        data = cg.get_coins_markets(vs_currency='usd', order='market_cap_desc', per_page=100, page=1)
        df = pd.DataFrame(data)
        df = df[['id', 'symbol', 'name', 'current_price', 'price_change_percentage_24h']]
        df = df.sort_values(by='price_change_percentage_24h', ascending=False)
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки списка: {e}")
        return pd.DataFrame(columns=['id', 'symbol', 'name', 'current_price', 'price_change_percentage_24h'])

@st.cache_data(ttl=300)
def load_binance_klines(symbol, interval, limit=1000):
    """Загружает свечи через прямой запрос к Binance API (без сторонних библиотек)"""
    try:
        url = f"{BINANCE_API_URL}/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        # Увеличиваем таймаут и добавляем заголовки
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        klines = response.json()

        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки данных Binance: {e}")
        return pd.DataFrame()

# ------------------ ЗАГРУЗКА СПИСКА МОНЕТ ------------------
df_coins = load_coins_list()

# ------------------ ИНТЕРФЕЙС: ДВЕ КОЛОНКИ ------------------
col_chart, col_list = st.columns([5, 1.2])

# ------------------ ПРАВАЯ КОЛОНКА (СПИСОК) ------------------
with col_list:
    st.markdown("### 🔥 Рост за 24ч")

    if df_coins.empty:
        st.warning("Нет данных")
    else:
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
        selected_symbol = 'BTC'
        if event.selection.rows:
            idx = event.selection.rows[0]
            selected_symbol = df_coins.iloc[idx]['symbol'].upper()

# ------------------ ЛЕВАЯ КОЛОНКА (ГРАФИК) ------------------
with col_chart:
    # Заголовок и таймфрейм в одной строке
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.markdown(f"### {selected_symbol}/USDT")
    with header_col2:
        timeframe = st.selectbox(
            "Таймфрейм",
            options=['1m', '5m', '30m', '1h', '4h'],
            index=1  # 5m по умолчанию
        )

    # Загружаем данные
    binance_symbol = f"{selected_symbol}USDT"
    df = load_binance_klines(binance_symbol, interval=timeframe, limit=1000)

    if not df.empty:
        # Создаём график
        fig = go.Figure()

        # Свечи
        fig.add_trace(go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Цена',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
            showlegend=True
        ))

        # EMA 65 (оранжевый)
        df['EMA_65'] = df['close'].ewm(span=65, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['EMA_65'],
            name='EMA 65',
            line=dict(color='#FFA500', width=1.5)
        ))

        # EMA 125 (синий)
        df['EMA_125'] = df['close'].ewm(span=125, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['EMA_125'],
            name='EMA 125',
            line=dict(color='#1E90FF', width=1.5)
        ))

        # EMA 450 (розовый)
        df['EMA_450'] = df['close'].ewm(span=450, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['EMA_450'],
            name='EMA 450',
            line=dict(color='#FF69B4', width=1.5)
        ))

        # Оформление в стиле TradingView
        fig.update_layout(
            template="plotly_dark",
            height=800,
            margin=dict(l=20, r=20, t=40, b=20),
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0
            ),
            xaxis_rangeslider_visible=False,
            xaxis=dict(
                type='category',      # убирает разрывы из-за нерабочих дней
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)'
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)',
                side='right'           # шкала справа, как на TradingView
            ),
            plot_bgcolor='#0e1117',
            paper_bgcolor='#0e1117'
        )

        # Убираем лишние элементы
        fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
        fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Не удалось загрузить график. Попробуйте другую монету.")
