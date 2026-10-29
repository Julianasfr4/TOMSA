"""
Auditoria dos dados originais de cada robô (antes da reamostragem):
saltos de GPS, falhas de dados (dropouts) e acelerações anómalas.
Todas usam diferenças finitas entre amostras consecutivas.
"""

import datetime

import numpy as np


def _hora_utc(timestamp_unix):
    return datetime.datetime.fromtimestamp(timestamp_unix, datetime.timezone.utc).strftime('%H:%M:%S UTC')


def detetar_anomalias_gps(dados_brutos, limiar_vel_ms=10.0):
    """Saltos de posição: velocidade aparente ‖Δp‖/Δt acima do limiar físico."""
    anomalias = []
    for id_robo, df in dados_brutos.items():
        dt = df['tempo_segundos'].diff()
        dist = np.sqrt(df['N_metros'].diff()**2 + df['E_metros'].diff()**2 + df['D_metros'].diff()**2)
        vel_calculada = dist / dt

        for idx in df.index[(vel_calculada > limiar_vel_ms) & (dt > 0)]:
            linha = df.loc[idx]
            anomalias.append({
                'robo': id_robo,
                'tempo_s': round(float(linha['tempo_segundos']), 1),
                'hora_utc': _hora_utc(linha['timestamp_unix']),
                'vel_salto': round(float(vel_calculada.loc[idx]), 1),
                'lat': round(float(linha['lat']), 6),
                'lon': round(float(linha['lon']), 6),
            })
    return anomalias


def detetar_dropouts(dados_brutos, dropout_min_s=2.0):
    """Falhas de dados: intervalos entre amostras consecutivas maiores do que dropout_min_s."""
    falhas = []
    for id_robo, df in dados_brutos.items():
        dt = df['tempo_segundos'].diff()
        for idx in df.index[dt > dropout_min_s]:
            falhas.append({
                'robo': id_robo,
                'inicio_s': round(float(df.loc[idx - 1, 'tempo_segundos']), 1),
                'duracao_s': round(float(dt.loc[idx]), 1),
                'hora_utc': _hora_utc(df.loc[idx - 1, 'timestamp_unix']),
            })
    return falhas


def detetar_aceleracoes(dados_brutos, limiar_ms2=1.0):
    """Acelerações anómalas: |Δv/Δt| da velocidade escalar acima do limiar."""
    eventos = []
    for id_robo, df in dados_brutos.items():
        dt = df['tempo_segundos'].diff()
        acel = df['velocidade_ms'].diff() / dt
        for idx in df.index[(acel.abs() > limiar_ms2) & (dt > 0)]:
            eventos.append({
                'robo': id_robo,
                'tempo_s': round(float(df.loc[idx, 'tempo_segundos']), 1),
                'hora_utc': _hora_utc(df.loc[idx, 'timestamp_unix']),
                'aceleracao_ms2': round(float(acel.loc[idx]), 2),
            })
    return eventos
