"""
Callbacks do Dash: replay, mapa, radar, telemetria, DCPA/TCPA, IA, log e exportações.
"""

import datetime

import dash
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yaml
from scipy.spatial.transform import Rotation as R
from dash import html, dcc, Input, Output, State, Patch

from ai.ia_local import explicar_situacao
from ai.voz import audio_da_explicacao
from analysis.risco import calcular_dcpa_tcpa
from io_dados.exportacao import tabela_telemetria, relatorio_missao
from geo.transformacoes import ned_para_aer, ned_para_corpo, ned_para_corpo_completo
from io_dados.leitor import estado_no_instante
from ui.estilo import *
from ui.graficos import criar_figura_validacao_velocidade

def roll_pitch(estado):
    """Roll e pitch (graus) a partir do quaternion do estado (sequência 'ZYX': yaw, pitch, roll)."""
    _, pitch, roll = R.from_quat([estado['qx'], estado['qy'], estado['qz'], estado['qw']]).as_euler('ZYX', degrees=True)
    return roll, pitch


def ler_tempo(texto):
    """Converte '1800', '30:00' ou '0:30:00' em segundos de missão. Devolve None se o texto não for válido."""
    try:
        partes = [float(p) for p in str(texto).strip().split(':')]
    except ValueError:
        return None
    if not 1 <= len(partes) <= 3 or any(p < 0 for p in partes):
        return None
    segundos = 0.0
    for p in partes:
        segundos = segundos * 60 + p
    return int(segundos)


# Velocidades do replay: segundos de missão por cada segundo real
VELOCIDADES = [1, 5, 10]


def registar_callbacks(app, m):
    """Liga os callbacks à app. 'm' tem os dados da missão já carregados (ver app.py)."""
    config = m['config']
    dados_robos = m['dados']
    nomes_robos = m['nomes_robos']
    cores_robos = m['cores']
    anomalias_gps = m['resumo']['saltos_gps']
    tempo_maximo = m['tempo_maximo']
    lat_origem = config['referencia_superficie']['lat']
    lon_origem = config['referencia_superficie']['lon']
    pares = [(a, b) for i, a in enumerate(nomes_robos) for b in nomes_robos[i + 1:]]

    def hora_utc(t, formato='%H:%M:%S'):
        return datetime.datetime.fromtimestamp(m['t0_unix'] + t, datetime.timezone.utc).strftime(formato)

    # --- 6.1 Play / Pause ---
    # Alterna entre reproduzir e pausar ligando/desligando o relógio
    @app.callback(
        Output('relogio-missao', 'disabled'),
        Output('botao-play', 'children'),
        Input('botao-play', 'n_clicks'),
        State('relogio-missao', 'disabled'),
        prevent_initial_call=True
    )
    def alternar_play_pause(n_clicks, relogio_parado):
        # Se o relógio estava parado, ligamos o relógio (disabled=False) e o botão mostra "Pausa"
        if relogio_parado:
            return False, "Pausa"
        # Se já estava a correr, paramos o relógio (disabled=True) e o botão volta a mostrar "Play"
        else:
            return True, "Play"


    # --- 6.2 Avançar o tempo a cada tick do relógio ---
    @app.callback(
        Output('slider-tempo', 'value'),
        Input('relogio-missao', 'n_intervals'),
        State('slider-tempo', 'value'),
        State('seletor-velocidade', 'value'),
        prevent_initial_call=True
    )
    def avancar_tempo(ticks, tempo_atual, velocidade):
        # Cada tick dura 1 s real e avança "velocidade" segundos de missão (1×, 5× ou 10×)
        novo_tempo = tempo_atual + velocidade

        # Se atingir o fim da missão, recomeça do início
        if novo_tempo > tempo_maximo:
            novo_tempo = 0

        return novo_tempo


    # --- 6.2b Saltar para um instante escrito pelo utilizador ---
    @app.callback(
        Output('slider-tempo', 'value', allow_duplicate=True),
        Input('botao-ir', 'n_clicks'),
        Input('entrada-tempo', 'n_submit'),
        State('entrada-tempo', 'value'),
        prevent_initial_call=True
    )
    def saltar_para_instante(n_clicks, n_submit, texto):
        segundos = ler_tempo(texto)
        if segundos is None:
            return dash.no_update
        return min(segundos, tempo_maximo)


    # --- 6.3 Texto do tempo de missão ---
    @app.callback(
        Output('texto-tempo', 'children'),
        Input('slider-tempo', 'value')
    )
    def atualizar_texto_tempo(valor):
        if valor is None:
            return dash.no_update
        return f"Missão: {datetime.timedelta(seconds=int(valor))} ({valor} s)"


    # --- 6.4 Marcadores no mapa global ---
    @app.callback(
        Output('grafico-mapa', 'figure'),
        Input('slider-tempo', 'value')
    )
    def animar_robos(tempo_atual):
        if tempo_atual is None:
            return dash.no_update

        meu_patch = Patch()
        indice_base_marcadores = len(nomes_robos) + 1

        for i, id_robo in enumerate(nomes_robos):
            ultima = estado_no_instante(dados_robos[id_robo], tempo_atual)
            idx = indice_base_marcadores + i
            # Robô sem dados neste instante (ainda não começou ou já terminou): esconder o marcador
            meu_patch["data"][idx]["lat"] = [] if ultima is None else [ultima["lat"]]
            meu_patch["data"][idx]["lon"] = [] if ultima is None else [ultima["lon"]]

        return meu_patch


    # --- 6.5 Radar 3D no referencial do corpo ---
    def figura_vazia(mensagem):
        fig = go.Figure()
        fig.update_layout(
            template="plotly_white", height=380, margin=dict(l=0, r=0, t=10, b=0),
            annotations=[dict(text=mensagem, showarrow=False, font=dict(color=COR_SUAVE))],
            xaxis=dict(visible=False), yaxis=dict(visible=False)
        )
        return fig


    @app.callback(
        Output('grafico-radar', 'figure'),
        Input('slider-tempo', 'value'),
        Input('seletor-robo', 'value'),
        Input('modo-radar', 'value'),
        Input('rotacao-radar', 'value')
    )
    def atualizar_radar(tempo_atual, ego_robo, modo, rotacao):
        if tempo_atual is None or ego_robo is None:
            return dash.no_update

        ego_atual = estado_no_instante(dados_robos[ego_robo], tempo_atual)
        if ego_atual is None:
            return figura_vazia(f"{ego_robo} não tem dados neste instante")

        # Todos os robôs (incluindo o próprio) até ao instante atual, vistos a partir da pose atual
        lista_dfs = []
        for id_robo in nomes_robos:
            df = dados_robos[id_robo]
            if id_robo != ego_robo and estado_no_instante(df, tempo_atual) is None:
                continue
            historico = df[df['tempo_segundos'] <= tempo_atual].dropna(subset=['N_metros'])

            dn = historico['N_metros'].values - ego_atual['N_metros']
            de = historico['E_metros'].values - ego_atual['E_metros']
            dd = historico['D_metros'].values - ego_atual['D_metros']
            if rotacao == 'completa':
                quat = [ego_atual['qx'], ego_atual['qy'], ego_atual['qz'], ego_atual['qw']]
                frente, direita, cima = ned_para_corpo_completo(dn, de, dd, quat)
            else:
                frente, direita, cima = ned_para_corpo(dn, de, dd, ego_atual['heading'])
            lista_dfs.append(pd.DataFrame({
                'Robo': f"{id_robo} (percurso)" if id_robo == ego_robo else id_robo,
                'Frente (m)': frente, 'Direita (m)': direita, 'Cima (m)': cima
            }))

        df_radar = pd.concat(lista_dfs)
        cores = {**cores_robos, f"{ego_robo} (percurso)": cores_robos[ego_robo]}

        alcance = max(10.0, float(np.abs(df_radar[['Frente (m)', 'Direita (m)']].values).max()) * 0.25)
        if modo == '2d':
            return radar_2d(df_radar, cores, ego_robo, ego_atual['heading'], alcance)
        return radar_3d(df_radar, cores, ego_robo, ego_atual['heading'], alcance)

    def radar_3d(df_radar, cores, ego_robo, heading, alcance):
        fig_radar = px.line_3d(
            df_radar, x='Direita (m)', y='Frente (m)', z='Cima (m)',
            color='Robo',
            color_discrete_map=cores,
            height=380
        )

        # Seta do heading: o eixo "Frente" do robô de referência
        fig_radar.add_trace(go.Scatter3d(
            x=[0, 0], y=[0, alcance], z=[0, 0],
            mode='lines', line=dict(color=COR_TEXTO, width=6),
            showlegend=False, hoverinfo='skip'
        ))
        fig_radar.add_trace(go.Cone(
            x=[0], y=[alcance], z=[0], u=[0], v=[1], w=[0],
            anchor='tip', sizemode='absolute', sizeref=alcance * 0.25,
            colorscale=[[0, COR_TEXTO], [1, COR_TEXTO]], showscale=False, hoverinfo='skip'
        ))

        fig_radar.add_trace(go.Scatter3d(
            x=[0], y=[0], z=[0],
            mode='markers+text',
            marker=dict(size=6, color=COR_TEXTO, symbol='diamond'),
            text=[f"{ego_robo} ({heading:.0f}°)"], textposition="top center",
            showlegend=False
        ))

        fig_radar.update_layout(
            template="plotly_white",
            margin=dict(l=0, r=0, t=10, b=0),
            scene=dict(
                xaxis_title="Direita (m)",
                yaxis_title="Frente (m)",
                zaxis_title="Cima (m)",
                camera=dict(eye=dict(x=1.6, y=1.6, z=0.6))
            ),
            legend=dict(title=None, orientation="h", y=1.02, x=0)
        )
        return fig_radar

    def radar_2d(df_radar, cores, ego_robo, heading, alcance):
        # Vista de cima: a frente do robô aponta sempre para cima no gráfico
        fig_radar = px.line(
            df_radar, x='Direita (m)', y='Frente (m)',
            color='Robo', color_discrete_map=cores, height=380
        )
        fig_radar.add_annotation(
            x=0, y=alcance, ax=0, ay=0, xref='x', yref='y', axref='x', ayref='y',
            showarrow=True, arrowhead=3, arrowwidth=2, arrowcolor=COR_TEXTO, text=""
        )
        fig_radar.add_trace(go.Scatter(
            x=[0], y=[0], mode='markers+text',
            marker=dict(size=10, color=COR_TEXTO, symbol='diamond'),
            text=[f"{ego_robo} ({heading:.0f}°)"], textposition="bottom center",
            showlegend=False
        ))
        fig_radar.update_layout(
            template="plotly_white",
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(title=None, orientation="h", y=1.02, x=0)
        )
        fig_radar.update_yaxes(scaleanchor='x', scaleratio=1)   # mesma escala nos dois eixos
        return fig_radar


    # --- 6.5b Estado de todos os robôs e linha do instante nos gráficos temporais ---
    @app.callback(
        Output('tabela-estado-robos', 'children'),
        Output('grafico-profundidade', 'figure'),
        Output('grafico-velocidade', 'figure'),
        Output('grafico-distancias', 'figure'),
        Input('slider-tempo', 'value')
    )
    def atualizar_estado_robos(tempo_atual):
        if tempo_atual is None:
            return (dash.no_update,) * 4

        estilo_celula = {'padding': '4px 12px 4px 0', 'borderBottom': f'1px solid {COR_BORDA}'}
        cabecalho = ["Robô", "Profundidade D", "Velocidade", "Rumo", "Dist. à origem"]
        linhas = []
        for id_robo in nomes_robos:
            e = estado_no_instante(dados_robos[id_robo], tempo_atual)
            if e is None:
                valores = ["sem dados"] + [""] * 3
            else:
                valores = [f"{e['D_metros']:.1f} m", f"{e['velocidade_ms']:.2f} m/s",
                           f"{e['heading']:.0f}°", f"{e['distancia_origem_m']:.1f} m"]
            linhas.append(html.Tr(
                [html.Td(id_robo, style={**estilo_celula, 'color': cores_robos[id_robo], 'fontWeight': '600'})] +
                [html.Td(v, style=estilo_celula) for v in valores]
            ))
        tabela = html.Table([
            html.Thead(html.Tr([html.Th(h, style={**estilo_celula, 'color': COR_SUAVE, 'textAlign': 'left', 'fontWeight': '400'})
                                for h in cabecalho])),
            html.Tbody(linhas)
        ], style={'fontSize': '13px', 'borderCollapse': 'collapse'})

        # Só a linha vertical muda; as curvas ficam como estão
        linha = Patch()
        linha['layout']['shapes'][0]['x0'] = tempo_atual
        linha['layout']['shapes'][0]['x1'] = tempo_atual
        return tabela, linha, linha, linha


    # --- 6.5c Validação da velocidade do robô de referência ---
    @app.callback(
        Output('grafico-validacao-velocidade', 'figure'),
        Input('seletor-robo', 'value')
    )
    def atualizar_validacao(ego_robo):
        return criar_figura_validacao_velocidade(dados_robos[ego_robo], cores_robos[ego_robo], ego_robo)


    # --- 6.6 Telemetria e coordenadas AER ---
    @app.callback(
        Output('painel-telemetria', 'children'),
        Input('slider-tempo', 'value'),
        Input('seletor-robo', 'value')
    )
    def atualizar_telemetria(tempo_atual, ego_robo):
        if tempo_atual is None or ego_robo is None:
            return "Sem dados"

        linha = estado_no_instante(dados_robos[ego_robo], tempo_atual)
        if linha is None:
            return html.Div(f"{ego_robo} não tem dados neste instante.", style={'color': COR_SUAVE})

        estilo_celula = {'padding': '3px 8px 3px 0'}
        estilo_rotulo = {**estilo_celula, 'color': COR_SUAVE}

        def linha_info(label, valor):
            return html.Tr([html.Td(label, style=estilo_rotulo), html.Td(valor, style={**estilo_celula, 'fontWeight': '600'})])

        tabela_ego = html.Table(html.Tbody([
            linha_info("Heading", f"{linha['heading']:.1f}°"),
            linha_info("Roll / Pitch", "{:.1f}° / {:.1f}°".format(*roll_pitch(linha))),
            linha_info("Velocidade", f"{linha['velocidade_ms']:.2f} m/s"),
            linha_info("Dist. à origem", f"{linha['distancia_origem_m']:.1f} m"),
            linha_info("Posição NED", f"N={linha['N_metros']:.1f} m, E={linha['E_metros']:.1f} m, D={linha['D_metros']:.2f} m"),
        ]), style={'fontSize': '13px', 'borderCollapse': 'collapse', 'marginBottom': '8px'})

        linhas_aer = []
        for id_viz in nomes_robos:
            if id_viz == ego_robo:
                continue
            viz_atual = estado_no_instante(dados_robos[id_viz], tempo_atual)
            if viz_atual is None:
                continue

            dn = viz_atual['N_metros'] - linha['N_metros']
            de = viz_atual['E_metros'] - linha['E_metros']
            dd = viz_atual['D_metros'] - linha['D_metros']

            azimuth, elevation, slant_range = ned_para_aer(dn, de, dd)

            alerta_prox = slant_range < 20.0
            cor_txt = CORES_RISCO['CRÍTICO'] if alerta_prox else COR_TEXTO

            linhas_aer.append(html.Tr([
                html.Td(id_viz, style={**estilo_celula, 'color': cores_robos.get(id_viz, COR_TEXTO), 'fontWeight': '600'}),
                html.Td(f"{azimuth:.0f}°", style=estilo_celula),
                html.Td(f"{elevation:.1f}°", style=estilo_celula),
                html.Td(f"{slant_range:.1f} m" + (" (perto)" if alerta_prox else ""), style={**estilo_celula, 'color': cor_txt}),
            ]))

        if not linhas_aer:
            return html.Div([tabela_ego, html.Div("Sem vizinhos ativos neste instante.", style={'color': COR_SUAVE})])

        tabela_aer = html.Table([
            html.Thead(html.Tr([html.Th(h, style={**estilo_rotulo, 'textAlign': 'left', 'fontWeight': '400'})
                                for h in ["Vizinho", "Azimute", "Elevação", "Distância"]])),
            html.Tbody(linhas_aer)
        ], style={'fontSize': '13px', 'borderCollapse': 'collapse'})

        return html.Div([tabela_ego, html.H4("Vizinhos em coordenadas AER", style=ESTILO_SUBTITULO), tabela_aer])


    # --- 6.7 Tabela DCPA / TCPA ---
    @app.callback(
        Output('painel-dcpa-tcpa', 'children'),
        Input('slider-tempo', 'value')
    )
    def atualizar_matriz_dcpa(tempo_atual):
        if tempo_atual is None:
            return "A aguardar dados..."
        t = int(tempo_atual)

        pos = {}
        vel = {}
        for rid in nomes_robos:
            u = estado_no_instante(dados_robos[rid], t)
            if u is not None:
                psi = np.radians(u['heading'])
                v = u['velocidade_ms']
                pos[rid] = (u['N_metros'], u['E_metros'])
                vel[rid] = (v * np.cos(psi), v * np.sin(psi))

        estilo_celula = {'padding': '6px 8px', 'borderBottom': f'1px solid {COR_BORDA}'}
        linhas_tabela = []

        for rA, rB in pares:
            if rA in pos and rB in pos:
                dist, dcpa, tcpa, st, risco = calcular_dcpa_tcpa(pos[rA], vel[rA], pos[rB], vel[rB])
                tcpa_txt = f"{tcpa:.1f} s" if tcpa >= 0 else "—"

                linhas_tabela.append(html.Tr([
                    html.Td(f"{rA} ↔ {rB}", style={**estilo_celula, 'fontWeight': '600'}),
                    html.Td(f"{dist:.1f} m", style=estilo_celula),
                    html.Td(f"{dcpa:.1f} m", style=estilo_celula),
                    html.Td(tcpa_txt, style=estilo_celula),
                    html.Td(st, style=estilo_celula),
                    html.Td(risco, style={**estilo_celula, 'color': CORES_RISCO.get(risco, COR_TEXTO), 'fontWeight': '600'})
                ]))

        if not linhas_tabela:
            return html.Div("Menos de dois robôs com dados neste instante.", style={'color': COR_SUAVE})

        cabecalho = ["Par", "Dist. atual", "Dist. mínima prevista", "Tempo até lá", "Dinâmica", "Risco"]
        return html.Table([
            html.Thead(html.Tr([html.Th(h, style={**estilo_celula, 'color': COR_SUAVE, 'textAlign': 'left', 'fontWeight': '400'})
                                for h in cabecalho])),
            html.Tbody(linhas_tabela)
        ], style={'width': '100%', 'fontSize': '13px', 'borderCollapse': 'collapse'})


    # --- 6.8 Explicação por IA (Ollama ou API, com texto por regras se não responder) ---
    # O servidor do Dash trata cada pedido numa thread própria, por isso o replay continua
    # enquanto o modelo responde; o botão fica desativado até chegar a resposta.
    @app.callback(
        Output('caixa-narrativa-ia', 'children'),
        Input('btn-explicar-ia', 'n_clicks'),
        State('slider-tempo', 'value'),
        State('seletor-robo', 'value'),
        running=[(Output('btn-explicar-ia', 'disabled'), True, False)],
        prevent_initial_call=True
    )
    def explicar_situacao_ia(n_clicks, tempo_atual, ego_robo):
        tempo = tempo_atual if tempo_atual is not None else 0
        ego = ego_robo if ego_robo is not None else nomes_robos[0]
        texto, _origem = explicar_situacao(dados_robos, tempo, ego, anomalias_gps, config['ia'])
        return texto


    # --- 6.8b Ler a explicação em voz alta (espeak-ng no servidor, sem internet) ---
    @app.callback(
        Output('audio-ia', 'src'),
        Output('aviso-voz', 'children'),
        Input('btn-ouvir-ia', 'n_clicks'),
        State('caixa-narrativa-ia', 'children'),
        running=[(Output('btn-ouvir-ia', 'disabled'), True, False)],
        prevent_initial_call=True
    )
    def ouvir_explicacao(n_clicks, texto):
        return audio_da_explicacao(texto)


    # --- 6.9 Log de eventos ---
    @app.callback(
        Output('caixa-log-eventos', 'children'),
        Input('slider-tempo', 'value')
    )
    def atualizar_log_eventos(tempo_atual):
        if tempo_atual is None:
            return "A aguardar eventos..."
        t = int(tempo_atual)
        hora = hora_utc(t)

        logs = [
            f"[{hora} UTC | t={t}s] Sistema ativo. Origem NED fixa na Aguçadoura (Lat: {lat_origem:.4f}°, Lon: {lon_origem:.4f}°)."
        ]

        posicoes = {}
        for id_r in nomes_robos:
            ult = estado_no_instante(dados_robos[id_r], t)
            if ult is not None:
                posicoes[id_r] = (ult['N_metros'], ult['E_metros'], ult['D_metros'])
            else:
                logs.append(f"[{hora} UTC] {id_r}: sem dados neste instante.")

        for rA, rB in pares:
            if rA in posicoes and rB in posicoes:
                pA = posicoes[rA]
                pB = posicoes[rB]
                dist = np.sqrt((pA[0]-pB[0])**2 + (pA[1]-pB[1])**2 + (pA[2]-pB[2])**2)
                if dist < 20.0:
                    logs.append(f"[{hora} UTC] ALERTA DE PROXIMIDADE: {rA} ↔ {rB} a {dist:.1f} m")
                else:
                    logs.append(f"[{hora} UTC] Separação {rA} ↔ {rB}: {dist:.1f} m")

        return [html.Div(msg) for msg in logs]

    # --- 6.10 Exportações CSV, TXT e YAML (requisito 5) ---
    @app.callback(
        Output('download-telemetria-csv', 'data'),
        Input('btn-exportar-csv', 'n_clicks'),
        prevent_initial_call=True
    )
    def exportar_telemetria_csv(n_clicks):
        # Campos, referencial, taxa e intervalo vêm da secção 'saida' do config.yaml
        tabela = tabela_telemetria(dados_robos, config['saida'], config['reamostragem']['passo_s'])
        return dcc.send_data_frame(tabela.to_csv, "telemetria_tomsa.csv", index=False)

    @app.callback(
        Output('download-log-txt', 'data'),
        Input('btn-exportar-log', 'n_clicks'),
        State('slider-tempo', 'value'),
        prevent_initial_call=True
    )
    def exportar_relatorio(n_clicks, tempo_atual):
        tempo = tempo_atual if tempo_atual is not None else 0
        texto = relatorio_missao(dados_robos, config, tempo, hora_utc(tempo, '%Y-%m-%d %H:%M:%S UTC'), m['resumo'])
        return dcc.send_string(texto, filename=f"relatorio_missao_t{int(tempo)}s.txt")

    @app.callback(
        Output('download-config-yaml', 'data'),
        Input('btn-exportar-yaml', 'n_clicks'),
        prevent_initial_call=True
    )
    def exportar_config_yaml(n_clicks):
        conteudo = yaml.dump(config, sort_keys=False, allow_unicode=True)
        return dcc.send_string(conteudo, filename="config_missao_tomsa.yaml")
