"""
Reamostragem de todos os robôs numa grelha temporal comum.

Posição, velocidade e tempo absoluto são interpolados linearmente; a orientação é
interpolada por SLERP (interpolação esférica de quaternions), que evita os saltos de
360° de interpolar ângulos diretamente. Instantes dentro de uma falha de dados maior do
que falha_max_s ficam vazios (NaN), em vez de inventar uma trajetória.
"""

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R, Slerp

from geo.transformacoes import heading_de_quaternion

COLUNAS_LINEARES = ['timestamp_unix', 'lat', 'lon', 'alt', 'N_metros', 'E_metros', 'D_metros', 'velocidade_ms']


def grelha_comum(dados_brutos, passo_s):
    """Instantes 0, passo, 2·passo, ... até ao fim do último robô."""
    t_fim = max(df['tempo_segundos'].iloc[-1] for df in dados_brutos.values())
    return np.arange(0.0, t_fim + passo_s, passo_s)


def mascara_valida(tempos, grelha, falha_max_s):
    """True nos instantes da grelha que caem entre duas amostras separadas por <= falha_max_s."""
    i = np.searchsorted(tempos, grelha, side='right') - 1
    dentro = (i >= 0) & (i < len(tempos) - 1)
    valida = np.zeros(len(grelha), dtype=bool)
    valida[dentro] = (tempos[i[dentro] + 1] - tempos[i[dentro]]) <= falha_max_s
    valida |= np.isin(grelha, tempos)   # instantes que coincidem com amostras reais
    return valida


def reamostrar_robo(df, grelha, falha_max_s, convencao='ned'):
    tempos = df['tempo_segundos'].values
    valida = mascara_valida(tempos, grelha, falha_max_s)
    t_val = grelha[valida]

    out = pd.DataFrame({'tempo_segundos': grelha})
    for col in COLUNAS_LINEARES:
        out[col] = np.nan
        out.loc[valida, col] = np.interp(t_val, tempos, df[col].values)

    out['heading'] = np.nan
    for q in ['qx', 'qy', 'qz', 'qw']:
        out[q] = np.nan
    if len(t_val):
        slerp = Slerp(tempos, R.from_quat(df[['qx', 'qy', 'qz', 'qw']].values))
        quats = slerp(t_val).as_quat()
        out.loc[valida, ['qx', 'qy', 'qz', 'qw']] = quats
        out.loc[valida, 'heading'] = heading_de_quaternion(quats, convencao)

    out['distancia_origem_m'] = np.hypot(out['N_metros'], out['E_metros'])
    out['tempo_real_unix'] = out['timestamp_unix']
    return out


def reamostrar_missao(dados_brutos, config):
    """Devolve {id_robo: DataFrame na grelha comum} e a própria grelha."""
    passo = config['reamostragem']['passo_s']
    falha_max = config['reamostragem']['falha_max_s']
    convencoes = {r['id']: r['convencao_orientacao'] for r in config['robos']}
    grelha = grelha_comum(dados_brutos, passo)
    return {rid: reamostrar_robo(df, grelha, falha_max, convencoes[rid]) for rid, df in dados_brutos.items()}, grelha
