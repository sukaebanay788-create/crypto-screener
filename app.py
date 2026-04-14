# ... (код до создания fig)

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
        showlegend=True,
        hoverinfo='none'          # отключаем всплывающую табличку
    ))

    df['EMA_65'] = df['close'].ewm(span=65, adjust=False).mean()
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['EMA_65'],
        name='EMA 65',
        line=dict(color='#FFA500', width=1.5),
        hoverinfo='none'
    ))

    df['EMA_125'] = df['close'].ewm(span=125, adjust=False).mean()
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['EMA_125'],
        name='EMA 125',
        line=dict(color='#1E90FF', width=1.5),
        hoverinfo='none'
    ))

    df['EMA_450'] = df['close'].ewm(span=450, adjust=False).mean()
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['EMA_450'],
        name='EMA 450',
        line=dict(color='#FF69B4', width=1.5),
        hoverinfo='none'
    ))

    # Настройки графика
    fig.update_layout(
        template="plotly_dark",
        height=800,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode='x',                 # оставляем только вертикальную линию
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            type='category',
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            side='right'
        ),
        plot_bgcolor='#0e1117',
        paper_bgcolor='#0e1117',
        dragmode=False                 # отключаем перемещение, разрешаем зум за оси
    )

    fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
    fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)

    # Конфигурация отображения
    config = {
        'displayModeBar': False,
        'scrollZoom': True,
        'displaylogo': False
    }

    st.plotly_chart(fig, use_container_width=True, config=config)
else:
    st.warning("Не удалось загрузить график. Попробуйте другую монету.")
