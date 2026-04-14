import streamlit as st
import pandas as pd
from pycoingecko import CoinGeckoAPI
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Настройка широкого экрана
st.set_page_config(layout="wide")

# API CoinGecko
cg = CoinGeckoAPI()

# --- Загрузка списка монет (кэш на 60 секунд) ---
@st.cache_data(ttl=60)
def load_coins_list():
    data = cg.get_coins_markets(vs_currency='usd', order='market_cap_desc', per_page=100, page=1)
    df = pd.DataFrame(data)
    df = df[['id', 'symbol', 'name', 'current_price', 'price_change_percentage_24h']]
    df = df.sort_values(by='price_change_percentage_24h', ascending=False)
    return df

# --- Загрузка исторических данных для графика ---
@st.cache_data(ttl=300)
def load_chart_data(coin_id, days=7):
    hist = cg.get_coin_market_chart_by_id(id=coin_id, vs_currency='usd', days=days)
    df = pd.DataFrame(hist['prices'], columns=['timestamp', 'price'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# --- Получаем данные ---
df_coins = load_coins_list()

# --- Интерфейс: две колонки ---
col_chart, col_list = st.columns([5, 1.5])

# --- ПРАВАЯ КОЛОНКА: СПИСОК МОНЕТ ---
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
    
    selected_coin_id = 'bitcoin'
    selected_symbol = 'BTC'
    
    if event.selection.rows:
        idx = event.selection.rows[0]
        selected_coin_id = df_coins.iloc[idx]['id']
        selected_symbol = df_coins.iloc[idx]['symbol'].upper()

# --- ЛЕВАЯ КОЛОНКА: ГРАФИК С ИНДИКАТОРАМИ ---
with col_chart:
    st.markdown(f"### {selected_symbol}/USD")
    df_chart = load_chart_data(selected_coin_id)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.02,
                        row_heights=[0.8, 0.2])
    
    # Цена
    fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['price'],
                             name='Цена', line=dict(color='white')), row=1, col=1)
    
    # Скользящие средние
    df_chart['SMA_20'] = df_chart['price'].rolling(window=20).mean()
    df_chart['SMA_50'] = df_chart['price'].rolling(window=50).mean()
    
    fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['SMA_20'],
                             name='SMA 20', line=dict(color='orange', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['SMA_50'],
                             name='SMA 50', line=dict(color='blue', width=1)), row=1, col=1)
    
    # RSI
    delta = df_chart['price'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_chart['RSI'] = 100 - (100 / (1 + rs))
    
    fig.add_trace(go.Scatter(x=df_chart['timestamp'], y=df_chart['RSI'],
                             name='RSI 14', line=dict(color='purple')), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    
    fig.update_layout(
        template="plotly_dark",
        height=800,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode='x unified',
        showlegend=True
    )
    fig.update_xaxes(title_text="Время", row=2, col=1)
    fig.update_yaxes(title_text="Цена (USD)", row=1, col=1)
    fig.update_yaxes(title_text="RSI", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)
