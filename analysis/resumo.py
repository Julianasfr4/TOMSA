"""
Indicadores da missão completa, calculados na grelha temporal comum.
"""

import numpy as np


def distancia_minima_pares(dados_grelha):
    """
    Para cada par de robôs: a menor distância 3D durante a missão e o instante em que ocorre,
    considerando só os instantes em que ambos têm dados.
    """
    ids = list(dados_grelha)
    resultado = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            da, db = dados_grelha[a], dados_grelha[b]
            dist = np.sqrt((da['N_metros'] - db['N_metros'])**2 +
                           (da['E_metros'] - db['E_metros'])**2 +
                           (da['D_metros'] - db['D_metros'])**2)
            if dist.notna().any():
                idx = dist.idxmin()
                resultado.append({'par': (a, b), 'distancia_m': round(float(dist[idx]), 1),
                                  'tempo_s': float(da.loc[idx, 'tempo_segundos'])})
            else:
                resultado.append({'par': (a, b), 'distancia_m': None, 'tempo_s': None})
    return resultado


def alertas_proximidade(dados_grelha, limiar_m=20.0):
    """
    Episódios em que um par de robôs esteve a menos de `limiar_m` (distância 3D):
    início e fim de cada episódio e a distância mínima atingida nele.
    """
    ids = list(dados_grelha)
    alertas = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            da, db = dados_grelha[a], dados_grelha[b]
            dist = np.sqrt((da['N_metros'] - db['N_metros'])**2 +
                           (da['E_metros'] - db['E_metros'])**2 +
                           (da['D_metros'] - db['D_metros'])**2)
            perto = (dist < limiar_m).to_numpy()
            # Cada episódio é um bloco contíguo de instantes abaixo do limiar
            mudancas = np.diff(np.concatenate(([0], perto.astype(int), [0])))
            for ini, fim in zip(np.flatnonzero(mudancas == 1), np.flatnonzero(mudancas == -1)):
                trecho = dist.iloc[ini:fim]
                idx = trecho.idxmin()
                alertas.append({'par': (a, b),
                                'inicio_s': float(da['tempo_segundos'].iloc[ini]),
                                'fim_s': float(da['tempo_segundos'].iloc[fim - 1]),
                                'distancia_m': round(float(trecho[idx]), 1),
                                'tempo_s': float(da.loc[idx, 'tempo_segundos'])})
    return sorted(alertas, key=lambda e: e['inicio_s'])
