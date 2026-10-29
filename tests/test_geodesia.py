"""
Testes unitários de transformações geodésicas e referenciais (TOMSA 2026)
A implementação própria (geo/transformacoes.py) é comparada com pymap3d e pyproj.
"""

import os
import sys
import pytest
import numpy as np
import pymap3d as pm
from pyproj import Transformer
from scipy.spatial.transform import Rotation as R

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from geo.transformacoes import lla2ecef, ecef2lla, lla2ned, ned2lla, matriz_ned, heading_de_quaternion, ned_para_corpo, ned_para_aer, ned_para_corpo_completo

# Origem de Referência na Aguçadoura (Surface Reference)
LAT0 = 41.45201666666667
LON0 = -8.81322222222222
ALT0 = 55.44791126176966

# Pontos de teste à volta da origem (até ~2 km) e em profundidade
LATS = LAT0 + np.array([0.0, 0.001, -0.005, 0.012, 0.0003])
LONS = LON0 + np.array([0.0, 0.0, 0.007, -0.015, 0.0002])
ALTS = ALT0 + np.array([0.0, 0.0, -30.0, 5.0, -12.5])


def test_origem_converte_para_zero():
    """A Surface Reference deve converter exatamente para (0, 0, 0) NED."""
    n, e, d = lla2ned(LAT0, LON0, ALT0, LAT0, LON0, ALT0)
    assert pytest.approx(n, abs=1e-6) == 0.0
    assert pytest.approx(e, abs=1e-6) == 0.0
    assert pytest.approx(d, abs=1e-6) == 0.0


def test_ecef_igual_ao_pyproj():
    """LLA → ECEF igual ao pyproj (EPSG:4979 → EPSG:4978) ao nível do milímetro."""
    t = Transformer.from_crs("EPSG:4979", "EPSG:4978", always_xy=True)
    x_ref, y_ref, z_ref = t.transform(LONS, LATS, ALTS)
    x, y, z = lla2ecef(LATS, LONS, ALTS)
    np.testing.assert_allclose(x, x_ref, atol=1e-3)
    np.testing.assert_allclose(y, y_ref, atol=1e-3)
    np.testing.assert_allclose(z, z_ref, atol=1e-3)


def test_ned_igual_ao_pymap3d():
    """LLA → NED igual ao pymap3d ao nível do milímetro."""
    n_ref, e_ref, d_ref = pm.geodetic2ned(LATS, LONS, ALTS, LAT0, LON0, ALT0)
    n, e, d = lla2ned(LATS, LONS, ALTS, LAT0, LON0, ALT0)
    np.testing.assert_allclose(n, n_ref, atol=1e-3)
    np.testing.assert_allclose(e, e_ref, atol=1e-3)
    np.testing.assert_allclose(d, d_ref, atol=1e-3)


def test_roundtrip_lla_ned_lla():
    """LLA → NED → LLA devolve os valores iniciais (erro < 1 mm)."""
    n, e, d = lla2ned(LATS, LONS, ALTS, LAT0, LON0, ALT0)
    lat, lon, alt = ned2lla(n, e, d, LAT0, LON0, ALT0)
    np.testing.assert_allclose(lat, LATS, atol=1e-9)   # 1e-9° ≈ 0,1 mm
    np.testing.assert_allclose(lon, LONS, atol=1e-9)
    np.testing.assert_allclose(alt, ALTS, atol=1e-4)


def test_roundtrip_ecef():
    lat, lon, alt = ecef2lla(*lla2ecef(LATS, LONS, ALTS))
    np.testing.assert_allclose(lat, LATS, atol=1e-10)
    np.testing.assert_allclose(alt, ALTS, atol=1e-4)


def test_matriz_ned_ortogonal():
    """R_ned é ortogonal: a inversa é a transposta."""
    r = matriz_ned(LAT0, LON0)
    np.testing.assert_allclose(r @ r.T, np.eye(3), atol=1e-12)


def test_um_grau_de_latitude():
    """1° de latitude a 41,45° N corresponde a ~111,1 km para Norte (WGS84)."""
    n, e, _ = lla2ned(LAT0 + 1.0, LON0, ALT0, LAT0, LON0, ALT0)
    assert 110_900 < n < 111_300
    assert abs(e) < 1.0


def test_deslocamento_este():
    """Um aumento de longitude dá E > 0 e N ≈ 0 (pequena curvatura)."""
    n, e, d = lla2ned(LAT0, LON0 + 0.001, ALT0, LAT0, LON0, ALT0)
    assert 80 < e < 85          # 111,3 km · cos(41,45°) · 0,001
    assert abs(n) < 0.01


def test_quaternion_para_heading():
    """Yaw de 30° em torno do eixo vertical: em NED o heading é o próprio yaw; em ENU é 90° - yaw."""
    quat = R.from_euler('z', 30, degrees=True).as_quat()
    assert pytest.approx(heading_de_quaternion([quat], 'ned')[0], abs=1e-6) == 30.0
    assert pytest.approx(heading_de_quaternion([quat], 'enu')[0], abs=1e-6) == 60.0


def test_referencial_do_corpo():
    """Robô virado a Este (heading 90°): um vizinho 10 m a Este fica 10 m à frente; um a Sul fica à direita."""
    frente, direita, cima = ned_para_corpo(np.array([0.0, -10.0]), np.array([10.0, 0.0]), np.array([0.0, 5.0]), 90.0)
    np.testing.assert_allclose(frente, [10.0, 0.0], atol=1e-9)
    np.testing.assert_allclose(direita, [0.0, 10.0], atol=1e-9)
    np.testing.assert_allclose(cima, [0.0, -5.0])          # 5 m mais fundo = 5 m abaixo


def test_rotacao_completa():
    """Só com yaw, a rotação completa dá o mesmo que a de yaw; com roll de 90°, a direita passa a ser 'cima'."""
    dn, de, dd = np.array([10.0, -3.0]), np.array([2.0, 7.0]), np.array([1.0, -4.0])
    q_yaw = R.from_euler('ZYX', [35, 0, 0], degrees=True).as_quat()
    np.testing.assert_allclose(ned_para_corpo_completo(dn, de, dd, q_yaw), ned_para_corpo(dn, de, dd, 35.0), atol=1e-9)

    q_roll = R.from_euler('ZYX', [0, 0, 90], degrees=True).as_quat()   # adornar 90° para estibordo
    frente, direita, cima = ned_para_corpo_completo([0.0], [0.0], [-5.0], q_roll)   # ponto 5 m acima
    np.testing.assert_allclose([frente[0], direita[0], cima[0]], [0.0, -5.0, 0.0], atol=1e-9)


def test_aer_igual_ao_pymap3d():
    """AER próprio igual ao ned2aer do pymap3d (azimute, elevação e distância)."""
    dn = np.array([10.0, -50.0, 0.0, 120.0, -3.0])
    de = np.array([0.0, 20.0, 40.0, -80.0, -4.0])
    dd = np.array([0.0, 5.0, -10.0, 30.0, 0.0])
    az, el, dist = ned_para_aer(dn, de, dd)
    az_ref, el_ref, dist_ref = pm.ned2aer(dn, de, dd)
    np.testing.assert_allclose(az, np.asarray(az_ref) % 360, atol=1e-9)
    np.testing.assert_allclose(el, el_ref, atol=1e-9)
    np.testing.assert_allclose(dist, dist_ref, atol=1e-9)


def test_heading_coerente_com_rumo_real():
    """
    Nos dados reais, o heading do quaternion deve coincidir com o rumo sobre o fundo (COG)
    calculado a partir das posições NED, quando o robô se desloca de forma clara.
    """
    from config.esquema import carregar_configuracao
    from io_dados.leitor import carregar_brutos

    config = carregar_configuracao()
    dados = carregar_brutos(config)
    for id_robo in ('robo_1', 'robo_4'):
        df = dados[id_robo].iloc[::10]                     # passos de ~1 s
        dn, de = df['N_metros'].diff(), df['E_metros'].diff()
        a_andar = np.hypot(dn, de) > 0.2
        cog = np.degrees(np.arctan2(de, dn)) % 360
        erro = ((df['heading'] - cog + 180) % 360 - 180).abs()[a_andar]
        assert len(erro) > 100
        assert erro.median() < 10.0, f"{id_robo}: erro mediano {erro.median():.1f}°"
