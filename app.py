import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from pycoingecko import CoinGeckoAPI
from datetime import datetime

# ------------------ НАСТРОЙКА СТРАНИЦЫ ------------------
st.set_page_config(
    page_title="Crypto Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ------------------ СТИЛИ (CSS для красоты) ------------------
st.markdown("""
<style>
    /* Убираем отступы и делаем интерфейс плотнее */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    /* Стили для заголовков */
    .stMarkdown h3 {
        margin-bottom: 0.5rem;
    }
    /* Таблица справа - убираем лишние границы */
    .stDataFrame {
        border: none;
    }
    /* Фон и цветовая схема */
    .stApp {
        background-color: #0e1117;
    }
</style>
""", unsafe_allow_html=True)

# ------------------ ИНИЦИАЛИЗАЦИЯ API ------------------
cg = CoinGeckoAPI()
OKX_API_URL = "https://www.okx.com/api/v5/market/history-candles"

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
def load_okx_klines(instId, bar="5m", limit=300):
    """Загружает свечи через OKX API (один запрос)"""
    try:
        params = {
            "instId": instId,
            "bar": bar,
            "limit": limit
        }
        response = requests.get(OKX_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data['code'] != '0':
            st.error(f"Ошибка API OKX: {data['msg']}")
            return pd.DataFrame()

        klines = data['data']
        klines.reverse()

        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'volCcy', 'volCcyQuote', 'confirm'])
        df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки данных OKX: {e}")
        return pd.DataFrame()

# ------------------ ЗАГРУЗКА СПИСКА МОНЕТ ------------------
df_coins = load_coins_list()

# ------------------ ИНТЕРФЕЙС: ДВЕ КОЛОНКИ ------------------
col_chart, col_list = st.columns([5, 1.2])

# ------------------ ПРАВАЯ КОЛОНКА (СПИСОК) ------------------
with col_list:
    st.markdown("### 🔥 Топ роста за 24ч")

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

        selected_symbol = 'BTC'
        if event.selection.rows:
            idx = event.selection.rows[0]
            selected_symbol = df_coins.iloc[idx]['symbol'].upper()

# ------------------ ЛЕВАЯ КОЛОНКА (ГРАФИК) ------------------
with col_chart:
    # Верхняя панель с названием и таймфреймом
    top_col1, top_col2, top_col3 = st.columns([2, 2, 1])
    with top_col1:
        st.markdown(f"## {selected_symbol}/USDT")
    with top_col3:
        timeframe = st.selectbox(
            "Таймфрейм",
            options=['1m', '5m', '30m', '1H', '4H'],
            index=1,
            label_visibility="collapsed"
        )

    # Загрузка данных
    okx_symbol = f"{selected_symbol}-USDT"
    df = load_okx_klines(okx_symbol, bar=timeframe, limit=300)

    if not df.empty:
        # Создаём фигуру
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
            showlegend=True,
            hoverinfo='x+y+open+high+low+close'
        ))

        # EMA 65
        df['EMA_65'] = df['close'].ewm(span=65, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['EMA_65'],
            name='EMA 65',
            line=dict(color='#FFA500', width=1.8),
            hoverinfo='none'
        ))

        # EMA 125
        df['EMA_125'] = df['close'].ewm(span=125, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['EMA_125'],
            name='EMA 125',
            line=dict(color='#1E90FF', width=1.8),
            hoverinfo='none'
        ))

        # EMA 450
        df['EMA_450'] = df['close'].ewm(span=450, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['EMA_450'],
            name='EMA 450',
            line=dict(color='#FF69B4', width=1.8),
            hoverinfo='none'
        ))

        # Настройки графика (стиль TradingView)
        fig.update_layout(
            template="plotly_dark",
            height=750,
            margin=dict(l=10, r=10, t=40, b=10),
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(0,0,0,0.3)',
                font=dict(size=12)
            ),
            xaxis_rangeslider_visible=False,
            xaxis=dict(
                type='category',
                showgrid=True,
                gridcolor='rgba(128,128,128,0.15)',
                gridwidth=0.5,
                zeroline=False,
                showline=True,
                linewidth=1,
                linecolor='rgba(128,128,128,0.5)',
                mirror=True
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(128,128,128,0.15)',
                gridwidth=0.5,
                zeroline=False,
                side='right',
                showline=True,
                linewidth=1,
                linecolor='rgba(128,128,128,0.5)',
                mirror=True
            ),
            plot_bgcolor='#0e1117',
            paper_bgcolor='#0e1117',
            dragmode='pan'
        )

        # Конфигурация (панель инструментов скрыта, но зум колесом работает)
        config = {
            'displayModeBar': False,
            'scrollZoom': True,
            'displaylogo': False
        }

        st.plotly_chart(fig, use_container_width=True, config=config)

        # Дополнительная информация (цена и изменение)
        col1, col2, col3 = st.columns(3)
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2] if len(df) > 1 else current_price
        change = current_price - prev_price
        change_percent = (change / prev_price) * 100 if prev_price != 0 else 0

        with col1:
            st.metric("Текущая цена", f"${current_price:,.4f}", 
                     delta=f"{change:+,.4f} ({change_percent:+.2f}%)")
        with col2:
            st.caption(f"Обновлено: {datetime.now().strftime('%H:%M:%S')}")
        with col3:
            st.caption(f"Таймфрейм: {timeframe}")
    else:
        st.warning("Не удалось загрузить график. Попробуйте другую монету.")
