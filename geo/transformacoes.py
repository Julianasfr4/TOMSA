"""
Transformações geodésicas (WGS84) e de orientação, implementadas em NumPy.

LLA (lat, lon, h) -> ECEF -> NED local, e o caminho inverso. O pymap3d e o pyproj
são usados apenas nos testes, como referência para validar estas fórmulas.
"""

import numpy as np
from scipy.spatial.transform import Rotation as R

# --- Elipsoide WGS84 ---
A = 6378137.0                  # semieixo maior (m)
F = 1 / 298.257223563          # achatamento
E2 = F * (2 - F)               # excentricidade ao quadrado
B = A * (1 - F)                # semieixo menor (m)


def lla2ecef(lat, lon, h):
    """Geodésicas (graus, graus, m) -> ECEF (m)."""
    lat, lon = np.radians(lat), np.radians(lon)
    n = A / np.sqrt(1 - E2 * np.sin(lat) ** 2)   # raio de curvatura na vertical principal
    x = (n + h) * np.cos(lat) * np.cos(lon)
    y = (n + h) * np.cos(lat) * np.sin(lon)
    z = (n * (1 - E2) + h) * np.sin(lat)
    return x, y, z


def ecef2lla(x, y, z, iteracoes=5):
    """ECEF (m) -> geodésicas (graus, graus, m), por iteração de ponto fixo na latitude."""
    x, y, z = np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)
    lon = np.arctan2(y, x)
    p = np.hypot(x, y)
    lat = np.arctan2(z, p * (1 - E2))            # aproximação inicial
    for _ in range(iteracoes):
        n = A / np.sqrt(1 - E2 * np.sin(lat) ** 2)
        h = p / np.cos(lat) - n
        lat = np.arctan2(z, p * (1 - E2 * n / (n + h)))
    n = A / np.sqrt(1 - E2 * np.sin(lat) ** 2)
    h = p / np.cos(lat) - n
    return np.degrees(lat), np.degrees(lon), h


def matriz_ned(lat0, lon0):
    """Matriz de rotação ECEF -> NED na origem (lat0, lon0). As linhas são os eixos N, E e D em ECEF."""
    lat0, lon0 = np.radians(lat0), np.radians(lon0)
    sf, cf, sl, cl = np.sin(lat0), np.cos(lat0), np.sin(lon0), np.cos(lon0)
    return np.array([
        [-sf * cl, -sf * sl,  cf],
        [-sl,       cl,       0.0],
        [-cf * cl, -cf * sl, -sf],
    ])


def lla2ned(lat, lon, h, lat0, lon0, h0):
    """Geodésicas -> NED (m) relativamente à origem (lat0, lon0, h0)."""
    p = np.vstack(lla2ecef(np.asarray(lat, float), np.asarray(lon, float), np.asarray(h, float)))
    p0 = np.array(lla2ecef(lat0, lon0, h0)).reshape(3, 1)
    n, e, d = matriz_ned(lat0, lon0) @ (p - p0)
    return n, e, d


def ned2lla(n, e, d, lat0, lon0, h0):
    """NED (m) -> geodésicas. Como a matriz é ortogonal, a inversa é a transposta."""
    ned = np.vstack([np.asarray(n, float), np.asarray(e, float), np.asarray(d, float)])
    p0 = np.array(lla2ecef(lat0, lon0, h0)).reshape(3, 1)
    x, y, z = matriz_ned(lat0, lon0).T @ ned + p0
    return ecef2lla(x, y, z)


def heading_de_quaternion(quats_xyzw, convencao='ned'):
    """
    Heading de bússola (0-360°, a partir do Norte, sentido horário) a partir de quaternions ROS (x, y, z, w).
    Em NED o yaw (sequência 'ZYX') já é o heading; em ENU o yaw conta a partir de Este, no sentido anti-horário.
    """
    yaw = R.from_quat(quats_xyzw).as_euler('ZYX', degrees=True)[:, 0]
    return (90 - yaw) % 360 if convencao == 'enu' else yaw % 360


def ned_para_corpo(dn, de, dd, heading_graus):
    """
    Diferenças NED -> referencial do corpo (frente, direita, cima), rodando só pelo heading (yaw).
    Roll e pitch ficam de fora: a vista local é no plano horizontal.
    """
    psi = np.radians(heading_graus)
    frente = dn * np.cos(psi) + de * np.sin(psi)
    direita = -dn * np.sin(psi) + de * np.cos(psi)
    return frente, direita, -np.asarray(dd)


def ned_para_aer(dn, de, dd):
    """
    Diferença NED -> AER: azimute (0-360°, a partir do Norte, sentido horário),
    elevação (positiva para cima) e distância 3D (slant range).
    """
    dn, de, dd = (np.asarray(v, float) for v in (dn, de, dd))
    horizontal = np.hypot(dn, de)
    azimute = np.degrees(np.arctan2(de, dn)) % 360
    elevacao = np.degrees(np.arctan2(-dd, horizontal))
    distancia = np.sqrt(horizontal**2 + dd**2)
    return azimute, elevacao, distancia


def ned_para_corpo_completo(dn, de, dd, quat_xyzw):
    """
    Diferenças NED -> referencial do corpo (frente, direita, cima) com a rotação completa
    (roll, pitch e yaw) do quaternion. O quaternion roda do corpo (FRD) para NED, por isso
    a passagem NED -> corpo é a rotação inversa: v_corpo = Rᵀ · v_NED.
    """
    v_ned = np.column_stack([np.atleast_1d(dn), np.atleast_1d(de), np.atleast_1d(dd)]).astype(float)
    v_corpo = R.from_quat(quat_xyzw).inv().apply(v_ned)
    return v_corpo[:, 0], v_corpo[:, 1], -v_corpo[:, 2]
