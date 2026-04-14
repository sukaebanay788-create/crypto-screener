import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from pycoingecko import CoinGeckoAPI
from datetime import datetime

# ------------------ НАСТРОЙКА СТРАНИЦЫ (Clean & Airy) ------------------
st.set_page_config(
    page_title="Crypto Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Убираем стандартные отступы Streamlit */
    .main .block-container {
        padding: 1rem 2rem 1rem 2rem;
        max-width: 100%;
    }
    /* Убираем стандартный футер и хедер */
    footer {visibility: hidden;}
    header {visibility: hidden;}
    /* Стиль для заголовков */
    h1, h2, h3 {
        font-family: 'Segoe UI', 'Roboto', sans-serif;
        font-weight: 300;
        letter-spacing: -0.01em;
    }
    /* Делаем таблицу более воздушной */
    .stDataFrame {
        font-family: 'Segoe UI', 'Roboto', sans-serif;
    }
    /* Стиль для метрик */
    .metric-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
        border: 1px solid #f0f0f0;
        text-align: center;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 300;
        color: #1a1a1a;
        line-height: 1.2;
    }
    .metric-delta {
        font-size: 0.9rem;
        color: #2ecc71;
    }
</style>
""", unsafe_allow_html=True)

# ------------------ API ------------------
cg = CoinGeckoAPI()
OKX_API_URL = "https://www.okx.com/api/v5/market/history-candles"

# ------------------ ФУНКЦИИ ------------------
@st.cache_data(ttl=60)
def load_coins_list():
    try:
        data = cg.get_coins_markets(vs_currency='usd', order='market_cap_desc', per_page=50, page=1)
        df = pd.DataFrame(data)
        df = df[['id', 'symbol', 'name', 'current_price', 'price_change_percentage_24h']]
        df = df.sort_values(by='price_change_percentage_24h', ascending=False)
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки списка: {e}")
        return pd.DataFrame(columns=['id', 'symbol', 'name', 'current_price', 'price_change_percentage_24h'])

@st.cache_data(ttl=300)
def load_okx_klines(instId, bar="5m", limit=300):
    try:
        params = {"instId": instId, "bar": bar, "limit": limit}
        response = requests.get(OKX_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data['code'] != '0':
            st.error(f"Ошибка OKX: {data['msg']}")
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

# ------------------ ЗАГРУЗКА СПИСКА ------------------
df_coins = load_coins_list()

# ------------------ ИНТЕРФЕЙС ------------------
# Используем больше воздуха между колонками
col_chart, col_spacer, col_list = st.columns([6, 0.1, 1.2])

# ------------------ ПРАВАЯ КОЛОНКА (СПИСОК) ------------------
with col_list:
    st.markdown("### Топ роста за 24ч")
    if df_coins.empty:
        st.warning("Нет данных")
    else:
        event = st.dataframe(
            df_coins[['symbol', 'price_change_percentage_24h']],
            column_config={
                "symbol": st.column_config.TextColumn("Монета", width="small"),
                "price_change_percentage_24h": st.column_config.NumberColumn("Рост %", format="%.2f %%", width="small")
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
    # Заголовок и выбор таймфрейма в одной строке
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        st.markdown(f"## {selected_symbol}/USDT")
    with c3:
        timeframe = st.selectbox("Таймфрейм", options=['1m', '5m', '30m', '1H', '4H'], index=1, label_visibility="collapsed")

    okx_symbol = f"{selected_symbol}-USDT"
    df = load_okx_klines(okx_symbol, bar=timeframe, limit=300)

    if not df.empty:
        fig = go.Figure()

        fig.add_trace(go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Цена',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
            showlegend=False  # Легенду не показываем, т.к. все подписано в названиях линий
        ))

        df['EMA_65'] = df['close'].ewm(span=65, adjust=False).mean()
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_65'], name='EMA 65', line=dict(color='#f39c12', width=1.5), hoverinfo='none'))

        df['EMA_125'] = df['close'].ewm(span=125, adjust=False).mean()
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_125'], name='EMA 125', line=dict(color='#2980b9', width=1.5), hoverinfo='none'))

        df['EMA_450'] = df['close'].ewm(span=450, adjust=False).mean()
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_450'], name='EMA 450', line=dict(color='#e74c3c', width=1.5), hoverinfo='none'))

        fig.update_layout(
            template="plotly_white",
            height=800,
            margin=dict(l=10, r=10, t=60, b=10),
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="top", y=1.15, xanchor="center", x=0.5, bgcolor='rgba(255,255,255,0.7)'),
            xaxis_rangeslider_visible=False,
            xaxis=dict(type='category', showgrid=False, showline=True, linewidth=1, linecolor='lightgray', mirror=True, ticks='outside', ticklen=8),
            yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.03)', side='right', showline=True, linewidth=1, linecolor='lightgray', mirror=True, ticks='outside', ticklen=8),
            plot_bgcolor='#ffffff',
            paper_bgcolor='#ffffff',
            dragmode='pan'
        )

        config = {'displayModeBar': False, 'scrollZoom': True, 'displaylogo': False}
        st.plotly_chart(fig, use_container_width=True, config=config)

        # Метрики в стиле "Clean & Airy"
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2] if len(df) > 1 else current_price
        change = current_price - prev_price
        change_percent = (change / prev_price) * 100 if prev_price != 0 else 0

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Текущая цена</div>
                <div class="metric-value">${current_price:,.2f}</div>
                <div class="metric-delta">{change:+,.2f} ({change_percent:+.2f}%)</div>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">24h максимум</div>
                <div class="metric-value">${df['high'].max():,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">24h минимум</div>
                <div class="metric-value">${df['low'].min():,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("Не удалось загрузить график.")
    else:
        st.warning("Не удалось загрузить график.")
