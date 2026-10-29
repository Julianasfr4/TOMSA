"""
Risco de aproximação entre robôs: DCPA / TCPA com modelo de velocidade constante.
"""

import numpy as np


def velocidade_ned(estado):
    """Vetor velocidade horizontal (vN, vE) assumindo deslocamento segundo o heading."""
    psi = np.radians(estado['heading'])
    v = estado['velocidade_ms']
    return (v * np.cos(psi), v * np.sin(psi))


def calcular_dcpa_tcpa(pA, vA, pB, vB):
    """
    Calcula a DCPA (Distance at Closest Point of Approach) e
    TCPA (Time to Closest Point of Approach) entre dois robôs:
    - pA, pB: tuplos (N, E) de posição no plano horizontal NED (metros)
    - vA, vB: tuplos (vN, vE) de velocidade vetorial (m/s)

    Devolve: (dist_atual, dcpa, tcpa, estado, nivel_risco)
    """
    p_rel = np.array(pB) - np.array(pA)
    v_rel = np.array(vB) - np.array(vA)

    dist_atual = float(np.linalg.norm(p_rel))
    v_rel_sq = float(np.dot(v_rel, v_rel))

    # Se a velocidade relativa é praticamente nula (paralelos ou parados)
    if v_rel_sq < 1e-4:
        return dist_atual, dist_atual, 0.0, "Paralelo / Estacionário", "SEGURO"

    tcpa = - float(np.dot(p_rel, v_rel)) / v_rel_sq

    if tcpa < 0:
        # Ponto de máxima aproximação já passou; estão a afastar-se
        return dist_atual, dist_atual, tcpa, "A Afastar-se", "SEGURO"
    else:
        # Estão a convergir
        p_cpa = p_rel + v_rel * tcpa
        dcpa = float(np.linalg.norm(p_cpa))

        if dcpa < 15.0 and tcpa < 60.0:
            risco = "CRÍTICO"
        elif dcpa < 25.0:
            risco = "ATENÇÃO"
        else:
            risco = "MODERADO"

        return dist_atual, dcpa, tcpa, "A Convergir", risco
