import streamlit as st
import pandas as pd
import requests
from pycoingecko import CoinGeckoAPI
from streamlit_lightweight_charts import render_lightweight_charts
import json

# ------------------ НАСТРОЙКА СТРАНИЦЫ (TradingView Style) ------------------
st.set_page_config(
    page_title="Crypto Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .main .block-container {
        padding: 0.5rem 0.5rem 0.5rem 0.5rem;
        max-width: 100%;
    }
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stApp {
        background-color: #131722;
    }
    h1, h2, h3, p, span, div, .stMarkdown {
        color: #d1d4dc;
        font-family: -apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif;
    }
    .stDataFrame {
        background-color: #1e222d;
        border-radius: 4px;
        border: 1px solid #2a2e39;
    }
    .stSelectbox > div > div {
        background-color: #1e222d;
        border: 1px solid #2a2e39;
        border-radius: 4px;
        color: #d1d4dc;
    }
    .tv-metric {
        background-color: #1e222d;
        border-radius: 4px;
        padding: 6px 12px;
        border: 1px solid #2a2e39;
    }
    .tv-label {
        font-size: 12px;
        color: #787b86;
    }
    .tv-value {
        font-size: 16px;
        font-weight: 600;
        color: #d1d4dc;
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

def calculate_ema(data, span):
    return data.ewm(span=span, adjust=False).mean()

# ------------------ ЗАГРУЗКА СПИСКА ------------------
df_coins = load_coins_list()

# ------------------ ИНТЕРФЕЙС ------------------
col_chart, col_list = st.columns([7, 1])

# ------------------ ПРАВАЯ КОЛОНКА (СПИСОК) ------------------
with col_list:
    st.markdown("<p style='margin-bottom: 5px; font-size: 13px; font-weight: 600; color: #787b86;'>ТОП РОСТА 24ч</p>", unsafe_allow_html=True)
    if df_coins.empty:
        st.warning("Нет данных")
    else:
        event = st.dataframe(
            df_coins[['symbol', 'price_change_percentage_24h']],
            column_config={
                "symbol": st.column_config.TextColumn("", width="small"),
                "price_change_percentage_24h": st.column_config.NumberColumn("", format="%.1f%%", width="small")
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
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(f"<span style='font-size: 20px; font-weight: 600;'>{selected_symbol}</span> <span style='color: #787b86;'>/ USDT</span>", unsafe_allow_html=True)
    with c2:
        timeframe = st.selectbox("", options=['1m', '5m', '30m', '1H', '4H'], index=1, label_visibility="collapsed")

    okx_symbol = f"{selected_symbol}-USDT"
    df = load_okx_klines(okx_symbol, bar=timeframe, limit=300)

    if not df.empty:
        # Подготовка данных для lightweight-charts
        chart_data = []
        for _, row in df.iterrows():
            chart_data.append({
                "time": int(row['timestamp'].timestamp()),
                "open": row['open'],
                "high": row['high'],
                "low": row['low'],
                "close": row['close']
            })

        ema_65 = calculate_ema(df['close'], 65)
        ema_125 = calculate_ema(df['close'], 125)
        ema_450 = calculate_ema(df['close'], 450)

        ema_65_data = [{"time": int(df['timestamp'].iloc[i].timestamp()), "value": ema_65.iloc[i]} for i in range(len(df)) if not pd.isna(ema_65.iloc[i])]
        ema_125_data = [{"time": int(df['timestamp'].iloc[i].timestamp()), "value": ema_125.iloc[i]} for i in range(len(df)) if not pd.isna(ema_125.iloc[i])]
        ema_450_data = [{"time": int(df['timestamp'].iloc[i].timestamp()), "value": ema_450.iloc[i]} for i in range(len(df)) if not pd.isna(ema_450.iloc[i])]

        chart_options = {
            "height": 750,
            "layout": {
                "background": {"color": "#131722"},
                "textColor": "#d1d4dc",
            },
            "grid": {
                "vertLines": {"color": "#2a2e39"},
                "horzLines": {"color": "#2a2e39"},
            },
            "crosshair": {
                "mode": 1,
                "vertLine": {"color": "#787b86", "width": 1, "style": 2},
                "horzLine": {"color": "#787b86", "width": 1, "style": 2},
            },
            "timeScale": {
                "timeVisible": True,
                "secondsVisible": False,
                "borderColor": "#2a2e39",
            },
            "rightPriceScale": {
                "borderColor": "#2a2e39",
                "scaleMargins": {
                    "top": 0.1,
                    "bottom": 0.1,
                },
            },
        }

        # Основная серия (свечи)
        series_candles = {
            "type": "Candlestick",
            "data": chart_data,
            "options": {
                "upColor": "#26a69a",
                "downColor": "#ef5350",
                "borderVisible": False,
                "wickUpColor": "#26a69a",
                "wickDownColor": "#ef5350",
            }
        }

        # Серии EMA
        series_ema_65 = {"type": "Line", "data": ema_65_data, "options": {"color": "#f39c12", "lineWidth": 1, "priceLineVisible": False, "lastValueVisible": False}}
        series_ema_125 = {"type": "Line", "data": ema_125_data, "options": {"color": "#3498db", "lineWidth": 1, "priceLineVisible": False, "lastValueVisible": False}}
        series_ema_450 = {"type": "Line", "data": ema_450_data, "options": {"color": "#e74c3c", "lineWidth": 1, "priceLineVisible": False, "lastValueVisible": False}}

        render_lightweight_charts([
            {"chart": chart_options, "series": [series_candles, series_ema_65, series_ema_125, series_ema_450]}
        ], 'chart')

        # Метрики в стиле TV
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2] if len(df) > 1 else current_price
        change = current_price - prev_price
        change_percent = (change / prev_price) * 100 if prev_price != 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""
            <div class="tv-metric">
                <div class="tv-label">O</div>
                <div class="tv-value">{df['open'].iloc[-1]:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="tv-metric">
                <div class="tv-label">H</div>
                <div class="tv-value">{df['high'].max():,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="tv-metric">
                <div class="tv-label">L</div>
                <div class="tv-value">{df['low'].min():,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with m4:
            st.markdown(f"""
            <div class="tv-metric">
                <div class="tv-label">C</div>
                <div class="tv-value">{current_price:,.2f}</div>
                <span style="color: {'#2ecc71' if change >=0 else '#e74c3c'}; font-size: 12px;">{change:+,.2f} ({change_percent:+.2f}%)</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("Не удалось загрузить график.")
