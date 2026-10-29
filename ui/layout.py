"""
Layout da página do dashboard.
"""

from dash import html, dcc

from ui.callbacks import VELOCIDADES
from ui.estilo import *


def resumo_missao(m):
    """Distância mínima entre cada par de robôs, falhas de dados e alertas de proximidade (< 20 m)."""
    linhas = [
        html.Div(f"{p['par'][0]} ↔ {p['par'][1]}: mínimo de {p['distancia_m']:.1f} m (t = {p['tempo_s']:.0f} s)")
        for p in m['resumo']['distancias_minimas'] if p['distancia_m'] is not None
    ]
    linhas.append(html.Div(f"Falhas de dados (dropouts): {len(m['resumo']['dropouts'])}"))

    alertas = m['resumo']['alertas_proximidade']
    linhas.append(html.Div(f"Alertas de proximidade (< 20 m): {len(alertas)}",
                           style={'fontWeight': '600', 'marginTop': '6px',
                                  'color': CORES_RISCO['CRÍTICO'] if alertas else CORES_RISCO['SEGURO']}))
    linhas += [
        html.Div(f"⚠ {a['par'][0]} ↔ {a['par'][1]}: t = {a['inicio_s']:.0f}–{a['fim_s']:.0f} s, "
                 f"mínimo de {a['distancia_m']:.1f} m (t = {a['tempo_s']:.0f} s)",
                 style={'color': CORES_RISCO['CRÍTICO']})
        for a in alertas
    ] if alertas else [html.Div("Os robôs nunca estiveram a menos de 20 m uns dos outros.", style={'color': COR_SUAVE})]
    return html.Div(linhas, style={'fontSize': '13px', 'lineHeight': '1.7'})


def validacao_velocidade(m):
    """Erro entre a velocidade medida (twist) e a obtida pelas posições, por robô."""
    return "Erro médio | mediano: " + " · ".join(
        f"{r} {v['erro_medio_ms']:.3f} | {v['erro_mediano_ms']:.3f} m/s" for r, v in m['resumo']['validacao_velocidade'].items()
    )


def criar_layout(m):
    return html.Div(
        style={
            'backgroundColor': COR_FUNDO, 'color': COR_TEXTO, 'minHeight': '100vh', 'padding': '20px',
            'fontFamily': 'system-ui, -apple-system, Segoe UI, sans-serif', 'fontSize': '14px'
        },
        children=[

            # Título
            html.Div([
                html.Div([
                    html.H1("Operação Aguçadoura — TOMSA 2026", style={'margin': '0', 'fontSize': '22px', 'fontWeight': '600'}),
                    html.P("Replay e análise da missão de 3 robôs marinhos · Grupo 20",
                           style={'margin': '4px 0 0 0', 'color': COR_SUAVE}),
                ]),
                # Logótipos (ficheiros na pasta assets/, servida automaticamente pelo Dash)
                html.Div([
                    html.Img(src=logo, style={'height': '58px', 'marginLeft': '22px'})
                    for logo in ['/assets/logo_isep.png', '/assets/logo_lsa.png', '/assets/logo_inesctec.png']
                ], style={'display': 'flex', 'alignItems': 'center'}),
            ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '16px'}),

            # Replay (no topo, porque controla todas as vistas)
            html.Div([
                html.Div([
                    html.Span(id='texto-tempo', children="Missão: 0:00:00", style={'fontWeight': '600'}),
                ], style={'marginBottom': '12px'}),

                dcc.Interval(id='relogio-missao', interval=1000, n_intervals=0, disabled=True),

                html.Div([
                    html.Button("Play", id='botao-play', n_clicks=0, style={'marginRight': '16px'}),
                    dcc.RadioItems(
                        id='seletor-velocidade',
                        options=[{'label': f"{v}×", 'value': v} for v in VELOCIDADES],
                        value=10, inline=True,
                        labelStyle={'marginRight': '10px'}, style={'marginRight': '16px'}
                    ),
                    dcc.Input(id='entrada-tempo', type='text', placeholder="ir para (s ou h:mm:ss)",
                              n_submit=0, style={'width': '150px', 'marginRight': '6px'}),
                    html.Button("Ir", id='botao-ir', n_clicks=0, style={'marginRight': '16px'}),
                    html.Div(
                        dcc.Slider(
                            id='slider-tempo',
                            min=0, max=m['tempo_maximo'], step=1, value=m['tempo_inicial'],
                            marks=None,
                            allow_direct_input=False,
                            updatemode="mouseup"
                        ),
                        style={'flexGrow': '1', 'minWidth': '0'}
                    )
                ], style={'display': 'flex', 'alignItems': 'center'})
            ], style=ESTILO_CARTAO),

            # Visão global (esq.) + visão local (dir.)
            html.Div([
                html.Div([
                    html.H3("Visão global (NED fixo na origem)", style=ESTILO_TITULO),
                    dcc.Graph(id='grafico-mapa', figure=m['fig_mapa']),
                    html.H4("Estado dos robôs no instante atual", style={**ESTILO_SUBTITULO, 'marginTop': '12px'}),
                    html.Div(id='tabela-estado-robos')
                ], style={**ESTILO_CARTAO, 'flex': '3', 'marginRight': '16px', 'minWidth': '0'}),

                html.Div([
                    html.H3("Visão local (referencial do corpo)", style=ESTILO_TITULO),
                    html.Div([
                        html.Label("Robô de referência", style={'color': COR_SUAVE, 'marginRight': '8px'}),
                        dcc.Dropdown(
                            id='seletor-robo',
                            options=[{'label': nome, 'value': nome} for nome in m['nomes_robos']],
                            value=m['nomes_robos'][0],
                            clearable=False,
                            style={'width': '160px'}
                        ),
                        dcc.RadioItems(
                            id='modo-radar',
                            options=[{'label': '3D', 'value': '3d'}, {'label': '2D (vista de cima)', 'value': '2d'}],
                            value='3d', inline=True,
                            labelStyle={'marginRight': '10px'}, style={'marginLeft': '16px'}
                        ),
                    ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '8px'}),
                    dcc.RadioItems(
                        id='rotacao-radar',
                        options=[{'label': 'Só yaw (plano horizontal)', 'value': 'yaw'},
                                 {'label': 'Rotação completa (roll, pitch, yaw)', 'value': 'completa'}],
                        value='yaw', inline=True,
                        labelStyle={'marginRight': '10px'}, style={'marginBottom': '4px', 'fontSize': '13px'}
                    ),
                    dcc.Graph(id='grafico-radar'),
                    html.Div(id='painel-telemetria', style={'marginTop': '8px'})
                ], style={**ESTILO_CARTAO, 'flex': '2', 'minWidth': '0'})
            ], style={'display': 'flex', 'alignItems': 'flex-start'}),

            # Estado de todos os robôs e evolução da profundidade e da velocidade
            html.Div([
                html.H3("Profundidade e velocidade dos robôs", style=ESTILO_TITULO),
                html.Div([
                    html.H4("Velocidade (m/s) ao longo da missão", style=ESTILO_SUBTITULO),
                    dcc.Graph(id='grafico-velocidade', figure=m['fig_velocidade'])
                ]),
                html.Div([
                    html.H4("Profundidade D (m) ao longo da missão", style=ESTILO_SUBTITULO),
                    dcc.Graph(id='grafico-profundidade', figure=m['fig_profundidade'])
                ], style={'marginTop': '8px'}),
                html.Div([
                    html.Div([
                        html.H4("Validação: velocidade medida vs derivada das posições (robô de referência)", style=ESTILO_SUBTITULO),
                        dcc.Graph(id='grafico-validacao-velocidade'),
                        html.Div(validacao_velocidade(m), style={'fontSize': '13px', 'color': COR_SUAVE})
                    ], style={'flex': '1', 'minWidth': '0'}),
                ], style={'display': 'flex', 'marginTop': '8px'})
            ], style=ESTILO_CARTAO),

            # Análise de proximidade (DCPA/TCPA) e saltos de GPS
            html.Div([
                html.H3("Análise de proximidade e segurança", style=ESTILO_TITULO),
                html.Div([
                    html.Div([
                        html.H4("Risco de colisão: distância mínima prevista e tempo até lá", style=ESTILO_SUBTITULO),
                        html.Div(id='painel-dcpa-tcpa'),
                        html.H4("Distância entre robôs ao longo da missão", style={**ESTILO_SUBTITULO, 'marginTop': '12px'}),
                        dcc.Graph(id='grafico-distancias', figure=m['fig_distancias'])
                    ], style={'flex': '3', 'marginRight': '24px', 'minWidth': '0'}),

                    html.Div([
                        html.H4("Saltos de GPS detetados", style=ESTILO_SUBTITULO),
                        html.Div([
                            html.Div([
                                html.Span(f"{a['hora_utc']}  ", style={'color': COR_SUAVE}),
                                html.Span(f"{a['robo']}", style={'color': m['cores'].get(a['robo'], COR_TEXTO), 'fontWeight': '600'}),
                                html.Span(f"  {a['vel_salto']} m/s aparentes")
                            ], style={'marginBottom': '4px', 'fontSize': '13px'}) for a in m['resumo']['saltos_gps']
                        ] if m['resumo']['saltos_gps'] else html.Div("Nenhum salto de GPS identificado.", style={'color': COR_SUAVE})),
                        html.H4("Resumo da missão completa", style={**ESTILO_SUBTITULO, 'marginTop': '12px'}),
                        resumo_missao(m)
                    ], style={'flex': '2', 'minWidth': '0'})
                ], style={'display': 'flex', 'marginBottom': '16px'}),

                # Copiloto de IA (Ollama ou API): explica em texto o instante selecionado
                botao("Explicar com IA", 'btn-explicar-ia', principal=True),
                botao("Ouvir", 'btn-ouvir-ia'),
                html.Span(id='aviso-voz', style={'color': COR_SUAVE, 'fontSize': '13px'}),
                html.Audio(id='audio-ia', autoPlay=True, controls=True, style={'display': 'block', 'margin': '4px 0 8px 0'}),
                dcc.Loading(
                    dcc.Markdown(
                        id='caixa-narrativa-ia',
                        children="Carrega em **Explicar com IA** para o copiloto de IA descrever o instante selecionado.",
                        style={'lineHeight': '1.6'}
                    ),
                    type='dot', color=COR_DESTAQUE
                ),
            ], style=ESTILO_CARTAO),

            # Registo de eventos e exportação (requisito 5)
            html.Div([
                html.H3("Registo e exportação", style=ESTILO_TITULO),
                html.Div([
                    botao("Exportar telemetria (CSV)", 'btn-exportar-csv'),
                    botao("Exportar relatório de missão (TXT)", 'btn-exportar-log'),
                    botao("Exportar configuração (YAML)", 'btn-exportar-yaml'),
                    dcc.Download(id='download-telemetria-csv'),
                    dcc.Download(id='download-log-txt'),
                    dcc.Download(id='download-config-yaml'),
                ], style={'display': 'flex', 'flexWrap': 'wrap'}),
                html.H4("Log de eventos", style={**ESTILO_SUBTITULO, 'marginTop': '8px'}),
                html.Div(id='caixa-log-eventos', style=ESTILO_CAIXA_TEXTO)
            ], style=ESTILO_CARTAO)
        ]
    )
