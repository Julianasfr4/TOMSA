"""
Validação cruzada da velocidade: a velocidade medida (twist, no referencial do corpo) deve
coincidir com a velocidade obtida derivando as posições NED no tempo (diferenças centrais
na grelha de 1 s, com média móvel para reduzir o ruído do GPS/USBL).
"""

import numpy as np
import pandas as pd

JANELA_S = 5


def velocidade_por_posicoes(df, janela=JANELA_S):
    """Norma de d(N, E, D)/dt na grelha comum, suavizada por média móvel centrada."""
    t = df['tempo_segundos'].values
    derivadas = [np.gradient(df[c].values, t) for c in ('N_metros', 'E_metros', 'D_metros')]
    v = np.sqrt(sum(d ** 2 for d in derivadas))
    return pd.Series(v, index=df.index).rolling(janela, center=True, min_periods=1).mean()


def comparar_velocidades(dados_grelha):
    """Para cada robô: erro médio absoluto e mediano (m/s) entre o twist e a derivada das posições."""
    resultado = {}
    for id_robo, df in dados_grelha.items():
        erro = (df['velocidade_ms'].rolling(JANELA_S, center=True, min_periods=1).mean()
                - velocidade_por_posicoes(df)).abs().dropna()
        resultado[id_robo] = {'erro_medio_ms': round(float(erro.mean()), 3),
                              'erro_mediano_ms': round(float(erro.median()), 3)}
    return resultado
