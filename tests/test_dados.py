"""
Testes da limpeza dos CSV, reamostragem (SLERP e falhas), auditoria de dados,
distância mínima, exportação configurável e modo offline do mapa (TOMSA 2026).
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation as R

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from analysis.anomalias import detetar_dropouts, detetar_aceleracoes, detetar_anomalias_gps
from analysis.reamostragem import reamostrar_robo, mascara_valida
from analysis.resumo import distancia_minima_pares
from io_dados.exportacao import tabela_telemetria
from io_dados.leitor import limpar_csv
from ui.callbacks import ler_tempo
from ui.graficos import criar_figura_serie
from ui.mapa import estilo_mapa, modo_offline

LAT0, LON0 = 41.452, -8.813


def _csv(n=5):
    """CSV mínimo no formato ROS, com n amostras espaçadas de 1 s."""
    q = R.from_euler('z', 0, degrees=True).as_quat()
    return pd.DataFrame({
        'header.stamp.secs': 1760095800 + np.arange(n), 'header.stamp.nsecs': 0,
        'pose.pose.position.x': LAT0, 'pose.pose.position.y': LON0, 'pose.pose.position.z': 55.0,
        'pose.pose.orientation.x': q[0], 'pose.pose.orientation.y': q[1],
        'pose.pose.orientation.z': q[2], 'pose.pose.orientation.w': q[3],
        'twist.twist.linear.x': 0.5, 'twist.twist.linear.y': 0.0, 'twist.twist.linear.z': 0.0,
    })


def _robo(tempos, n=None, vel=None, quats=None):
    """Robô já processado (como sai de io_dados.leitor.processar_robo)."""
    tempos = np.asarray(tempos, dtype=float)
    k = len(tempos)
    quats = np.tile([0, 0, 0, 1.0], (k, 1)) if quats is None else np.asarray(quats)
    return pd.DataFrame({
        'tempo_segundos': tempos, 'timestamp_unix': 1760095800 + tempos,
        'lat': LAT0, 'lon': LON0, 'alt': 55.0,
        'N_metros': tempos if n is None else n, 'E_metros': 0.0, 'D_metros': 0.0,
        'velocidade_ms': 1.0 if vel is None else vel,
        'qx': quats[:, 0], 'qy': quats[:, 1], 'qz': quats[:, 2], 'qw': quats[:, 3],
    })


# --- Limpeza ---

def test_limpeza_nan_e_duplicados():
    df = _csv(6)
    df.loc[2, 'pose.pose.position.x'] = np.nan          # linha com valor em falta
    df = pd.concat([df, df.iloc[[4]]])                   # timestamp repetido
    df = df.iloc[::-1]                                   # fora de ordem
    limpo, n_nan, n_dup = limpar_csv(df)
    assert (n_nan, n_dup) == (1, 1)
    assert len(limpo) == 5
    assert limpo['timestamp_unix'].is_monotonic_increasing


# --- Reamostragem ---

def test_slerp_atravessa_o_norte():
    """Entre 350° e 10° o SLERP passa por 0°, não por 180° (como faria interpolar ângulos)."""
    quats = R.from_euler('z', [[350], [10]], degrees=True).as_quat()
    df = _robo([0, 2], quats=quats)
    out = reamostrar_robo(df, np.array([0.0, 1.0, 2.0]), falha_max_s=5.0)
    meio = out['heading'].iloc[1]
    assert min(meio, 360 - meio) < 1e-6


def test_falha_longa_nao_e_interpolada():
    df = _robo([0, 1, 2, 20, 21])
    grelha = np.arange(0.0, 22.0)
    out = reamostrar_robo(df, grelha, falha_max_s=5.0)
    assert out.loc[out['tempo_segundos'].between(3, 19), 'N_metros'].isna().all()
    assert out.loc[out['tempo_segundos'].isin([0, 1, 2, 20, 21]), 'N_metros'].notna().all()


def test_mascara_fora_do_intervalo():
    valida = mascara_valida(np.array([10.0, 11.0, 12.0]), np.array([5.0, 10.0, 11.5, 12.0, 15.0]), 5.0)
    assert valida.tolist() == [False, True, True, True, False]


# --- Auditoria e resumo ---

def test_dropouts_e_aceleracoes():
    df = _robo([0, 1, 2, 6, 7], vel=[1.0, 1.0, 1.0, 1.0, 4.0])
    falhas = detetar_dropouts({'r': df}, dropout_min_s=2.0)
    assert len(falhas) == 1 and falhas[0]['inicio_s'] == 2.0 and falhas[0]['duracao_s'] == 4.0
    acel = detetar_aceleracoes({'r': df}, limiar_ms2=1.0)
    assert len(acel) == 1 and acel[0]['aceleracao_ms2'] == 3.0


def test_salto_gps():
    df = _robo([0, 1, 2, 3], n=[0.0, 1.0, 50.0, 51.0])
    saltos = detetar_anomalias_gps({'r': df}, limiar_vel_ms=10.0)
    assert len(saltos) == 1 and saltos[0]['tempo_s'] == 2.0


def test_distancia_minima():
    t = np.arange(0.0, 11.0)
    a = _robo(t, n=np.zeros(11))
    b = _robo(t, n=np.abs(t - 7) + 3)                    # mais perto em t = 7 s (3 m)
    b.loc[0, 'N_metros'] = np.nan
    [par] = distancia_minima_pares({'a': a, 'b': b})
    assert par['par'] == ('a', 'b') and par['distancia_m'] == 3.0 and par['tempo_s'] == 7.0


# --- Exportação ---

def _saida(**kw):
    return {'campos': ['velocidade_ms'], 'referencial': 'ned', 'taxa_hz': 1.0, 'intervalo_s': None, **kw}


def test_exportacao_referencial_e_campos():
    dados = {'r': _robo(np.arange(0.0, 10.0))}
    tab = tabela_telemetria(dados, _saida(), passo_s=1.0)
    assert list(tab.columns) == ['robo', 'tempo_s', 'hora_utc', 'N_metros', 'E_metros', 'D_metros', 'velocidade_ms']
    tab = tabela_telemetria(dados, _saida(referencial='ambos', campos=[]), passo_s=1.0)
    assert {'lat', 'lon', 'alt', 'N_metros'} <= set(tab.columns)


def test_exportacao_taxa_e_intervalo():
    dados = {'r': _robo(np.arange(0.0, 100.0))}
    tab = tabela_telemetria(dados, _saida(taxa_hz=0.1), passo_s=1.0)
    assert tab['tempo_s'].tolist()[:3] == [0.0, 10.0, 20.0]
    tab = tabela_telemetria(dados, _saida(intervalo_s=[20, 30]), passo_s=1.0)
    assert tab['tempo_s'].min() == 20.0 and tab['tempo_s'].max() == 30.0 and len(tab) == 11


# --- Mapa offline ---

def test_estilo_mapa_offline():
    assert estilo_mapa(True) == ("white-bg", [])
    estilo, camadas = estilo_mapa(False)
    assert estilo == "open-street-map" and 'openseamap' in camadas[0]['source'][0]
    assert modo_offline('sim') is True and modo_offline('nao') is False


# --- Saltar para um instante ---

def test_ler_tempo():
    assert ler_tempo("1800") == 1800
    assert ler_tempo("30:00") == 1800
    assert ler_tempo("1:02:03") == 3723
    assert ler_tempo("abc") is None and ler_tempo("-5") is None and ler_tempo("") is None


# --- Gráficos temporais ---

def test_figura_profundidade():
    dados = {'a': _robo(np.arange(0.0, 50.0)), 'b': _robo(np.arange(10.0, 30.0))}
    fig = criar_figura_serie(dados, {'a': '#111111', 'b': '#222222'}, 'D_metros', "D (m)", 12, inverter_y=True)
    assert [t.name for t in fig.data] == ['a', 'b']
    assert len(fig.data[0].x) == 10                       # 1 em cada 5 pontos
    assert fig.layout.shapes[0].x0 == 12                  # linha do instante atual
    assert fig.layout.yaxis.autorange == 'reversed'       # mais fundo = mais abaixo


# --- Validação da velocidade ---

def test_velocidade_por_posicoes():
    from analysis.validacao import velocidade_por_posicoes, comparar_velocidades
    t = np.arange(0.0, 60.0)
    df = _robo(t, n=0.5 * t, vel=np.full(len(t), 0.5))     # 0,5 m/s para Norte
    np.testing.assert_allclose(velocidade_por_posicoes(df).values, 0.5, atol=1e-9)
    assert comparar_velocidades({'r': df})['r']['erro_medio_ms'] == pytest.approx(0.0, abs=1e-9)


def test_figura_distancias():
    from ui.graficos import criar_figura_distancias
    t = np.arange(0.0, 20.0)
    fig = criar_figura_distancias({'a': _robo(t, n=np.zeros(20)), 'b': _robo(t, n=np.full(20, 30.0))}, 20.0)
    assert fig.data[0].name == "a ↔ b" and set(fig.data[0].y) == {30.0}
    assert fig.layout.shapes[1].y0 == 20.0                  # linha de alerta
