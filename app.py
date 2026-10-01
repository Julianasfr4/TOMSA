import dash
from dash import Dash, html, dcc, Input, Output, State, Patch
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import leitor_dados

print("🚀 A preparar os dados e a arrancar o servidor...")

# 1. Carregar os dados
config = leitor_dados.carregar_configuracao()
dados_robos = leitor_dados.carregar_csvs(config)
nomes_robos = list(dados_robos.keys())

tabelas_juntas = []
for id_robo, df in dados_robos.items():
    df_temp = df.copy()
    df_temp['Robo'] = id_robo
    tabelas_juntas.append(df_temp)

df_completo = pd.concat(tabelas_juntas)
tempo_maximo = int(df_completo['tempo_segundos'].max())

# 2. Criar o Mapa Base
fig_mapa = px.line_map(
    df_completo, lat="pose.pose.position.x", lon="pose.pose.position.y", 
    color="Robo", zoom=13, center={"lat": 41.452, "lon": -8.813}, height=600 
)

# 2.1 Pôr o rasto completo ligeiramente transparente
fig_mapa.update_traces(opacity=0.3) 

# 2.2 Adicionar "bolinhas" grossas para representar a posição atual de cada robô
# 2.2 Adicionar "bolinhas" grossas na posição inicial (Segundo 0)
cores_plotly = px.colors.qualitative.Plotly
for i, id_robo in enumerate(nomes_robos):
    # Vamos buscar logo a primeira linha de dados deste robô
    lat_inicial = dados_robos[id_robo].iloc[0]["pose.pose.position.x"]
    lon_inicial = dados_robos[id_robo].iloc[0]["pose.pose.position.y"]
    
    fig_mapa.add_trace(go.Scattermap(
        lat=[lat_inicial], lon=[lon_inicial], # Em vez de [None], pomos a posição inicial!
        mode="markers",
        marker=dict(size=14, color=cores_plotly[i % len(cores_plotly)]),
        name=f"{id_robo} (Atual)",
        showlegend=False
    ))

# 3. Iniciar o Dash
app = Dash(__name__)
app.index_string = '''<!DOCTYPE html>
<html lang="pt" translate="no">
<head>{%metas%}<title>TOMSA 2026</title>{%favicon%}{%css%}</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>'''

# 4. O Desenho da Página Web
app.layout = html.Div(style={'backgroundColor': '#111111', 'color': 'white', 'minHeight': '100vh', 'padding': '20px'}, children=[
    html.H1("🛰️ Operação Aguçadoura - TOMSA 2026", style={'textAlign': 'center', 'fontFamily': 'sans-serif'}),
    html.Hr(style={'borderColor': '#333'}),
    
    html.Div([
        dcc.Graph(id='grafico-mapa', figure=fig_mapa) # Demos um ID ao gráfico para o conseguirmos atualizar!
    ], style={'backgroundColor': '#1e1e1e', 'padding': '10px', 'borderRadius': '10px', 'marginBottom': '20px'}),
    
    html.Div([
        html.H4(id='texto-tempo', children="Tempo: 0 segundos", style={'margin': '0 0 10px 0', 'fontFamily': 'sans-serif'}),
        dcc.Interval(id='relogio-missao', interval=500, n_intervals=0, disabled=True),
        
        html.Div([
            html.Button("PLAY", id='botao-play', n_clicks=0, style={
                'flexShrink': '0', 'minWidth': '100px', 'marginRight': '20px',
                'padding': '10px 20px', 'fontSize': '16px', 'fontWeight': 'bold',
                'cursor': 'pointer', 'borderRadius': '5px',
                'border': '1px solid #888', 'backgroundColor': '#2d7ff9', 'color': 'white'
            }),
            html.Div(
                dcc.Slider(
                    id='slider-tempo', min=0, max=tempo_maximo, step=1, value=0,
                    tooltip={"placement": "bottom", "always_visible": True}
                ),
                style={'flexGrow': '1', 'minWidth': '0'} 
            )
        ], style={'display': 'flex', 'alignItems': 'center'})
    ], style={'backgroundColor': '#1e1e1e', 'padding': '20px', 'borderRadius': '10px'})
])

# 5. Callbacks

# Liga/Desliga relógio
@app.callback(
    Output('relogio-missao', 'disabled'), Output('botao-play', 'children'),
    Input('botao-play', 'n_clicks'), State('relogio-missao', 'disabled')
)
def pausar_reproducao(cliques, relogio_desligado):
    if cliques is None or cliques == 0:
        return dash.no_update, dash.no_update
    if relogio_desligado:
        return False, "PAUSE"
    return True, "PLAY"

# Avança o slider
@app.callback(
    Output('slider-tempo', 'value'),
    Input('relogio-missao', 'n_intervals'),
    State('slider-tempo', 'value')
)
def avancar_tempo(ticks, valor_atual):
    if ticks is None or ticks == 0:
        return dash.no_update
    novo_tempo = valor_atual + 5 
    if novo_tempo >= tempo_maximo:
        return 0
    return novo_tempo

# Atualiza o texto do tempo
@app.callback(
    Output('texto-tempo', 'children'),
    Input('slider-tempo', 'value')
)
def atualizar_texto(valor):
    if valor is None:
        return dash.no_update
    return f"Tempo da Missão: {valor} segundos"

# --- O CALLBACK DA MAGIA (Animação com Patch) ---
@app.callback(
    Output('grafico-mapa', 'figure'),
    Input('slider-tempo', 'value')
)
def animar_robos(tempo_atual):
    if tempo_atual is None:
        return dash.no_update
        
    meu_patch = Patch()
    
    # Para cada robô, vamos ver onde ele estava no segundo atual!
    for i, id_robo in enumerate(nomes_robos):
        df_robo = dados_robos[id_robo]
        
        # Filtramos a tabela para apanhar os dados SÓ até ao momento atual
        dados_passados = df_robo[df_robo['tempo_segundos'] <= tempo_atual]
        
        if not dados_passados.empty:
            # Apanhamos a última linha (a coordenada mais recente)
            ultima_linha = dados_passados.iloc[-1]
            lat_atual = ultima_linha["pose.pose.position.x"]
            lon_atual = ultima_linha["pose.pose.position.y"]
            
            # Os rastos no gráfico são as camadas 0, 1 e 2. 
            # As bolinhas que criámos são as camadas a seguir (índices 3, 4 e 5).
            indice_bolinha = len(nomes_robos) + i
            
            # Injetamos a coordenada na bolinha sem mexer no resto do mapa!
            meu_patch["data"][indice_bolinha]["lat"] = [lat_atual]
            meu_patch["data"][indice_bolinha]["lon"] = [lon_atual]
            
    return meu_patch

if __name__ == '__main__':
    print("🌍 Tudo pronto! Clica no link abaixo para veres o mapa:")
    app.run(debug=True)