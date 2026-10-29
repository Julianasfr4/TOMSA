"""
TOMSA 2026 - Dashboard de Missão de Robôs Marinhos
ISEP - Mestrado em Engenharia Eletrotécnica e de Computadores
Autores: Grupo 20 (Juliana Rodrigues)

Este ficheiro só carrega os dados e arranca a app. O resto está organizado em pacotes:
  config/    configuração YAML e validação (Pydantic)
  geo/       transformações LLA ↔ ECEF ↔ NED
  io_dados/  leitura e limpeza dos CSV, exportações
  analysis/  reamostragem, risco (DCPA/TCPA), anomalias e resumo da missão
  ai/        explicação por IA local (Ollama)
  ui/        layout, mapa e callbacks do Dash
"""

import os

import numpy as np
from dash import Dash

from analysis.anomalias import detetar_anomalias_gps, detetar_dropouts
from analysis.reamostragem import reamostrar_missao
from analysis.resumo import distancia_minima_pares, alertas_proximidade
from analysis.validacao import comparar_velocidades
from config.esquema import carregar_configuracao
from io_dados.leitor import carregar_brutos
from ui.callbacks import registar_callbacks
from ui.graficos import criar_figura_serie, criar_figura_distancias
from ui.layout import criar_layout
from ui.mapa import criar_figura_mapa, modo_offline

print("A preparar os dados e a arrancar o servidor...")

config = carregar_configuracao()
dados_brutos = carregar_brutos(config)
dados_robos, grelha = reamostrar_missao(dados_brutos, config)
cores_robos = {robo['id']: robo['cor'] for robo in config['robos'] if robo['id'] in dados_robos}

limiares = config['anomalias']
resumo = {
    'saltos_gps': detetar_anomalias_gps(dados_brutos, limiares['limiar_salto_ms']),
    'dropouts': detetar_dropouts(dados_brutos, limiares['dropout_min_s']),
    'distancias_minimas': distancia_minima_pares(dados_robos),
    'alertas_proximidade': alertas_proximidade(dados_robos, 20.0),
    'validacao_velocidade': comparar_velocidades(dados_robos),
}

offline = modo_offline(config['mapa']['offline'])
if offline:
    print("Sem internet: o mapa vai aparecer sem fundo.")

m = {
    'config': config,
    'dados': dados_robos,
    'nomes_robos': list(dados_robos),
    'cores': cores_robos,
    'resumo': resumo,
    't0_unix': min(df['timestamp_unix'].iloc[0] for df in dados_brutos.values()),
    'tempo_maximo': int(grelha[-1]),
    # Primeiro segundo em que todos os robôs já têm dados
    'tempo_inicial': int(np.ceil(max(df['tempo_segundos'].iloc[0] for df in dados_brutos.values()))),
    'fig_mapa': criar_figura_mapa(dados_robos, cores_robos, config['referencia_superficie'], offline),
}
m['fig_profundidade'] = criar_figura_serie(dados_robos, cores_robos, 'D_metros', "D (m)", m['tempo_inicial'], inverter_y=True)
m['fig_velocidade'] = criar_figura_serie(dados_robos, cores_robos, 'velocidade_ms', "Velocidade (m/s)", m['tempo_inicial'])
m['fig_distancias'] = criar_figura_distancias(dados_robos, 20.0, m['tempo_inicial'])

app = Dash(__name__)
app.index_string = '''<!DOCTYPE html>
<html lang="pt" translate="no">
<head>{%metas%}<title>TOMSA 2026</title>{%favicon%}{%css%}</head>
<body style="margin:0">{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>'''
app.layout = criar_layout(m)
registar_callbacks(app, m)

if __name__ == '__main__':
    # Modo de desenvolvimento só se pedido: TOMSA_DEBUG=1 python app.py
    app.run(debug=os.environ.get('TOMSA_DEBUG') == '1')
