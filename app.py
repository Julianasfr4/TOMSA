from dash import Dash, html, dcc
import plotly.express as px
import pandas as pd
import leitor_dados

print("🚀 A preparar os dados e a arrancar o servidor...")

# 1. Carregar os dados
config = leitor_dados.carregar_configuracao()
dados_robos = leitor_dados.carregar_csvs(config)

# 2. Juntar os dados de todos os robôs
tabelas_juntas = []
for id_robo, df in dados_robos.items():
    df_temp = df.copy()
    df_temp['Robo'] = id_robo
    tabelas_juntas.append(df_temp)

df_completo = pd.concat(tabelas_juntas)

# 3. Criar a "Global View" (O Mapa)
fig_mapa = px.line_map(
    df_completo, 
    lat="pose.pose.position.x", 
    lon="pose.pose.position.y", 
    color="Robo",
    zoom=13,
    center={"lat": 41.452, "lon": -8.813}, # Centro forçado na Aguçadoura
    height=700
)

# Aplicar o tema visual (Open Street Map)
# Aplicar o tema visual e a Carta Náutica
fig_mapa.update_layout(
    map_style="open-street-map",
    map_layers=[
        {
            "below": 'traces',          # Fica por baixo das linhas dos robôs
            "sourcetype": "raster",
            "sourceattribution": "OpenSeaMap",
            "source": [
                "https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png"
            ]
        }
    ],
    margin={"r":0,"t":0,"l":0,"b":0},
    paper_bgcolor="#111111",
    font_color="white",
    legend=dict(title="Equipa de Robôs", yanchor="top", y=0.99, xanchor="left", x=0.01)
)

# 4. Iniciar o Dash (Foi esta a linha que se tinha apagado!)
app = Dash(__name__)

# 5. O Desenho da Página Web
app.layout = html.Div(style={'backgroundColor': '#111111', 'color': 'white', 'minHeight': '100vh', 'padding': '20px'}, children=[
    html.H1("🛰️ Operação Aguçadoura - TOMSA 2026", style={'textAlign': 'center', 'fontFamily': 'sans-serif'}),
    html.Hr(style={'borderColor': '#333'}),
    
    html.Div([
        html.H3("🌍 Visão Global (Trajetórias Completas)"),
        dcc.Graph(figure=fig_mapa)
    ], style={'backgroundColor': '#1e1e1e', 'padding': '10px', 'borderRadius': '10px'})
])

# 6. Arrancar o servidor web
if __name__ == '__main__':
    print("🌍 Tudo pronto! Clica no link abaixo para veres o mapa:")
    app.run(debug=True)