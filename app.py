import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from pycoingecko import CoinGeckoAPI

# ------------------ НАСТРОЙКА СТРАНИЦЫ ------------------
st.set_page_config(layout="wide", page_title="Крипто-скринер")

# ------------------ API ------------------
cg = CoinGeckoAPI()
OKX_API_URL = "https://www.okx.com/api/v5/market/history-candles"

# ------------------ ФУНКЦИИ ------------------
@st.cache_data(ttl=60)
def load_coins_list():
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
# Колонки: график (широкая) и список (очень узкая)
col_chart, col_list = st.columns([6, 1])

# ------------------ ПРАВАЯ КОЛОНКА (СПИСОК) ------------------
with col_list:
    st.markdown("### 🔥 Рост 24ч")
    if df_coins.empty:
        st.warning("Нет данных")
    else:
        event = st.dataframe(
            df_coins[['symbol', 'price_change_percentage_24h']],
            column_config={
                "symbol": "Монета",
                "price_change_percentage_24h": st.column_config.NumberColumn("Рост %", format="%.2f %%")
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
    # Заголовок и выбор таймфрейма
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(f"## {selected_symbol}/USDT")
    with c2:
        timeframe = st.selectbox("Таймфрейм", options=['1m', '5m', '30m', '1H', '4H'], index=1, label_visibility="collapsed")

    # Загрузка свечей
    okx_symbol = f"{selected_symbol}-USDT"
    df = load_okx_klines(okx_symbol, bar=timeframe, limit=300)

    if not df.empty:
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

        # EMA 65
        df['EMA_65'] = df['close'].ewm(span=65, adjust=False).mean()
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_65'], name='EMA 65', line=dict(color='#FFA500', width=1.5), hoverinfo='none'))

        # EMA 125
        df['EMA_125'] = df['close'].ewm(span=125, adjust=False).mean()
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_125'], name='EMA 125', line=dict(color='#1E90FF', width=1.5), hoverinfo='none'))

        # EMA 450
        df['EMA_450'] = df['close'].ewm(span=450, adjust=False).mean()
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_450'], name='EMA 450', line=dict(color='#FF69B4', width=1.5), hoverinfo='none'))

        # Настройки графика
        fig.update_layout(
            template="plotly_dark",
            height=800,  # максимально используем высоту
            margin=dict(l=10, r=10, t=40, b=10),
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(0,0,0,0.3)'),
            xaxis_rangeslider_visible=False,
            xaxis=dict(type='category', showgrid=True, gridcolor='rgba(128,128,128,0.15)', showline=True, linewidth=1, linecolor='gray', mirror=True),
            yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.15)', side='right', showline=True, linewidth=1, linecolor='gray', mirror=True),
            plot_bgcolor='#0e1117',
            paper_bgcolor='#0e1117',
            dragmode='pan'
        )

        config = {'displayModeBar': False, 'scrollZoom': True, 'displaylogo': False}
        st.plotly_chart(fig, use_container_width=True, config=config)
    else:
        st.warning("Не удалось загрузить график.")
