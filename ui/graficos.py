"""
Gráficos da missão ao longo do tempo (profundidade e velocidade de cada robô).
As linhas são desenhadas uma só vez; o replay só move a linha vertical do instante atual.
"""

import plotly.graph_objects as go

from analysis.validacao import velocidade_por_posicoes

from ui.estilo import COR_TEXTO

# Amostra 1 em cada 5 pontos da grelha de 1 s: suficiente para ver a forma e mais leve no browser
PASSO_GRAFICO = 5


def criar_figura_serie(dados_robos, cores_robos, coluna, titulo_y, tempo_inicial=0, inverter_y=False):
    fig = go.Figure()
    for id_robo, df in dados_robos.items():
        sub = df.iloc[::PASSO_GRAFICO]
        fig.add_trace(go.Scatter(
            x=sub['tempo_segundos'], y=sub[coluna], mode='lines', name=id_robo,
            line=dict(color=cores_robos[id_robo], width=1.5)
        ))
    fig.update_layout(
        template="plotly_white", height=260, margin=dict(l=50, r=10, t=10, b=40),
        xaxis_title="Tempo de missão (s)", yaxis_title=titulo_y,
        legend=dict(orientation="h", y=1.08, x=0),
        # Linha vertical do instante atual (shapes[0]), movida pelo callback do replay
        shapes=[dict(type='line', xref='x', yref='paper', x0=tempo_inicial, x1=tempo_inicial,
                     y0=0, y1=1, line=dict(color=COR_TEXTO, width=1, dash='dot'))]
    )
    if inverter_y:
        fig.update_yaxes(autorange='reversed')   # mais fundo = mais abaixo
    return fig



def criar_figura_distancias(dados_robos, limiar_m=20.0, tempo_inicial=0):
    """Distância 3D entre cada par de robôs ao longo do tempo, com a linha de alerta."""
    ids = list(dados_robos)
    fig = go.Figure()
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            da, db = dados_robos[a].iloc[::PASSO_GRAFICO], dados_robos[b].iloc[::PASSO_GRAFICO]
            dist = ((da['N_metros'] - db['N_metros'])**2 + (da['E_metros'] - db['E_metros'])**2 +
                    (da['D_metros'] - db['D_metros'])**2) ** 0.5
            fig.add_trace(go.Scatter(x=da['tempo_segundos'], y=dist, mode='lines', name=f"{a} ↔ {b}", line=dict(width=1.5)))
    fig.update_layout(
        template="plotly_white", height=260, margin=dict(l=50, r=10, t=10, b=40),
        xaxis_title="Tempo de missão (s)", yaxis_title="Distância 3D (m)",
        legend=dict(orientation="h", y=1.08, x=0),
        shapes=[dict(type='line', xref='x', yref='paper', x0=tempo_inicial, x1=tempo_inicial,
                     y0=0, y1=1, line=dict(color=COR_TEXTO, width=1, dash='dot')),
                dict(type='line', xref='paper', yref='y', x0=0, x1=1, y0=limiar_m, y1=limiar_m,
                     line=dict(color='#c62828', width=1, dash='dash'))],
        annotations=[dict(xref='paper', yref='y', x=1, y=limiar_m, xanchor='right', yanchor='bottom',
                          text=f"alerta {limiar_m:.0f} m", showarrow=False, font=dict(color='#c62828', size=11))]
    )
    return fig


def criar_figura_validacao_velocidade(df, cor, id_robo):
    """Velocidade medida (twist) vs derivada das posições NED, para um robô."""
    sub = df.iloc[::PASSO_GRAFICO]
    v_pos = velocidade_por_posicoes(df).iloc[::PASSO_GRAFICO]
    fig = go.Figure([
        go.Scatter(x=sub['tempo_segundos'], y=sub['velocidade_ms'], mode='lines', name="twist (medida)",
                   line=dict(color=cor, width=1.5)),
        go.Scatter(x=sub['tempo_segundos'], y=v_pos, mode='lines', name="derivada das posições",
                   line=dict(color=COR_TEXTO, width=1, dash='dot')),
    ])
    fig.update_layout(template="plotly_white", height=260, margin=dict(l=50, r=10, t=10, b=40),
                      xaxis_title="Tempo de missão (s)", yaxis_title=f"Velocidade {id_robo} (m/s)",
                      legend=dict(orientation="h", y=1.08, x=0))
    return fig
