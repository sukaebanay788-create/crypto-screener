# Настройки графика
fig.update_layout(
    template="plotly_dark",
    height=800,
    margin=dict(l=20, r=20, t=40, b=20),
    hovermode='x unified',          # перекрестие при наведении
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
    dragmode='pan'                  # перемещение графика перетаскиванием мыши
)

fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)

# Конфигурация отображения
config = {
    'displayModeBar': False,    # полностью скрываем верхнюю панель инструментов
    'scrollZoom': True,         # зум колёсиком мыши
    'displaylogo': False        # убираем логотип Plotly
}

st.plotly_chart(fig, use_container_width=True, config=config)
