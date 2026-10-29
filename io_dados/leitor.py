"""
Leitura e limpeza dos CSV ROS de cada robô e conversão para NED, heading e velocidade.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from config.esquema import PASTA_PROJETO
from geo.transformacoes import lla2ned, heading_de_quaternion

COLUNAS_QUAT = ['pose.pose.orientation.x', 'pose.pose.orientation.y',
                'pose.pose.orientation.z', 'pose.pose.orientation.w']
COLUNAS_ESSENCIAIS = ['header.stamp.secs', 'header.stamp.nsecs', 'pose.pose.position.x',
                      'pose.pose.position.y', 'pose.pose.position.z'] + COLUNAS_QUAT


def limpar_csv(df):
    """
    Remove linhas com valores em falta nas colunas essenciais e timestamps duplicados,
    e ordena por tempo. Devolve (df_limpo, n_removidas_nan, n_removidas_duplicadas).
    """
    n_inicial = len(df)
    df = df.dropna(subset=COLUNAS_ESSENCIAIS)
    n_nan = n_inicial - len(df)

    df = df.assign(timestamp_unix=df['header.stamp.secs'] + df['header.stamp.nsecs'] * 1e-9)
    n_antes = len(df)
    df = df.drop_duplicates(subset='timestamp_unix', keep='first')
    n_duplicadas = n_antes - len(df)

    return df.sort_values('timestamp_unix').reset_index(drop=True), n_nan, n_duplicadas


def processar_robo(df, origem, convencao='ned'):
    """
    A partir de um CSV já limpo, calcula:
    lat/lon/alt, posição NED (implementação própria em geo/), quaternion, heading,
    velocidade escalar e distância horizontal à origem NED.
    """
    out = pd.DataFrame({
        'timestamp_unix': df['timestamp_unix'].values,
        'lat': df['pose.pose.position.x'].values,
        'lon': df['pose.pose.position.y'].values,
        'alt': df['pose.pose.position.z'].values,
    })

    n, e, d = lla2ned(out['lat'], out['lon'], out['alt'], origem['lat'], origem['lon'], origem['alt'])
    out['N_metros'], out['E_metros'], out['D_metros'] = n, e, d

    quats = df[COLUNAS_QUAT].values
    out[['qx', 'qy', 'qz', 'qw']] = quats
    out['heading'] = heading_de_quaternion(quats, convencao)

    # twist.linear está no referencial do corpo; a norma não depende do referencial
    v = df[['twist.twist.linear.x', 'twist.twist.linear.y', 'twist.twist.linear.z']].fillna(0).values
    out['velocidade_ms'] = np.linalg.norm(v, axis=1)

    out['distancia_origem_m'] = np.hypot(out['N_metros'], out['E_metros'])
    return out


def carregar_brutos(config):
    """
    Lê todos os CSV do config.yaml e devolve {id_robo: DataFrame} com as amostras originais.
    O tempo é contado a partir de um t0 comum (o primeiro registo de qualquer robô), para que
    o mesmo tempo_segundos corresponda ao mesmo instante real em todos os robôs.
    """
    dados = {}
    origem = config['referencia_superficie']

    for robo in config['robos']:
        caminho = Path(robo['ficheiro_csv'])
        if not caminho.is_absolute():
            caminho = PASTA_PROJETO / caminho
        try:
            df, n_nan, n_dup = limpar_csv(pd.read_csv(caminho))
        except FileNotFoundError:
            print(f"ERRO: ficheiro '{caminho}' não encontrado.")
            continue
        dados[robo['id']] = processar_robo(df, origem, robo['convencao_orientacao'])
        print(f"{robo['id']}: {len(df)} linhas ({n_nan} com valores em falta e {n_dup} duplicadas removidas)")

    if dados:
        t0_comum = min(df['timestamp_unix'].iloc[0] for df in dados.values())
        for df in dados.values():
            df['tempo_segundos'] = df['timestamp_unix'] - t0_comum
    return dados


def estado_no_instante(df, t):
    """
    Última amostra com tempo_segundos <= t, ou None se o robô ainda não começou, já terminou
    ou está numa falha de dados nesse instante.
    """
    tempos = df['tempo_segundos'].values
    if len(tempos) == 0 or t < tempos[0] or t > tempos[-1]:
        return None
    linha = df.iloc[int(np.searchsorted(tempos, t, side='right')) - 1]
    return None if pd.isna(linha['N_metros']) else linha
