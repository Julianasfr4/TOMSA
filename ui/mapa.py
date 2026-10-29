"""
Mapa global: trajetórias, origem NED e um marcador por robô (atualizado pelo replay).
Sem internet, o mapa usa um fundo branco sem mosaicos, para a app continuar a funcionar.
"""

import socket

import plotly.graph_objects as go

CAMADA_OPENSEAMAP = {
    "below": "traces",
    "sourcetype": "raster",
    "source": ["https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png"]
}


def internet_disponivel(host='tile.openstreetmap.org', porta=443, timeout_s=1.5):
    """Tenta abrir uma ligação ao servidor de mosaicos do OpenStreetMap."""
    try:
        socket.create_connection((host, porta), timeout=timeout_s).close()
        return True
    except OSError:
        return False


def modo_offline(opcao):
    """Converte a opção do config.yaml ('auto', 'sim' ou 'nao') num booleano."""
    if opcao == 'auto':
        return not internet_disponivel()
    return opcao == 'sim'


def estilo_mapa(offline):
    """Devolve (map_style, map_layers) para o modo pedido."""
    if offline:
        return "white-bg", []
    return "open-street-map", [CAMADA_OPENSEAMAP]


def criar_figura_mapa(dados_robos, cores_robos, origem, offline=False):
    fig = go.Figure()

    # Rastos (traços 0..n-1)
    for id_robo, df in dados_robos.items():
        fig.add_trace(go.Scattermap(
            lat=df['lat'], lon=df['lon'], mode="lines", opacity=0.4,
            line=dict(color=cores_robos[id_robo], width=2), name=id_robo
        ))

    # Origem NED (traço n)
    fig.add_trace(go.Scattermap(
        lat=[origem['lat']], lon=[origem['lon']],
        mode="markers+text", marker=dict(size=12, color='#1f2328'),
        text=["Origem NED"], textposition="top right", name="Origem NED"
    ))

    # Posição atual de cada robô (traços n+1..2n), preenchidos pelo callback do replay
    for id_robo in dados_robos:
        fig.add_trace(go.Scattermap(
            lat=[], lon=[], mode="markers",
            marker=dict(size=13, color=cores_robos[id_robo]),
            name=f"{id_robo} (posição atual)", showlegend=False
        ))

    estilo, camadas = estilo_mapa(offline)
    fig.update_layout(
        map=dict(style=estilo, layers=camadas, zoom=15, center={"lat": origem['lat'], "lon": origem['lon']}),
        height=520,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend=dict(title="Robô", yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(255,255,255,0.85)")
    )
    if offline:
        fig.add_annotation(text="Sem internet: mapa sem fundo", showarrow=False,
                           x=0.99, y=0.01, xref="paper", yref="paper", xanchor="right", yanchor="bottom")
    return fig
