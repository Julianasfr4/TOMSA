"""
Testes unitários dos cálculos vetoriais de DCPA, TCPA e AER (TOMSA 2026)
"""

import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from analysis.risco import calcular_dcpa_tcpa

def test_dcpa_tcpa_convergencia():
    """Dois robôs em rota de colisão frontal direta (head-on collision)."""
    pA = (0.0, 0.0)      # Robô A na origem
    vA = (1.0, 0.0)      # Robô A move-se para Norte a 1 m/s
    
    pB = (100.0, 0.0)    # Robô B a 100 m a Norte
    vB = (-1.0, 0.0)     # Robô B move-se para Sul a 1 m/s

    dist, dcpa, tcpa, estado, risco = calcular_dcpa_tcpa(pA, vA, pB, vB)

    assert pytest.approx(dist, abs=1e-5) == 100.0
    assert pytest.approx(dcpa, abs=1e-5) == 0.0     # Colisão direta em N=50
    assert pytest.approx(tcpa, abs=1e-5) == 50.0    # 100m / 2m/s = 50s
    assert estado == "A Convergir"
    assert risco in ["CRÍTICO", "ATENÇÃO"]

def test_dcpa_tcpa_afastamento():
    """Dois robôs a afastar-se no eixo Este-Oeste."""
    pA = (0.0, 0.0)
    vA = (0.0, -1.0)     # Robô A move-se para Oeste
    
    pB = (0.0, 50.0)
    vB = (0.0, 1.0)      # Robô B move-se para Este

    dist, dcpa, tcpa, estado, risco = calcular_dcpa_tcpa(pA, vA, pB, vB)

    assert pytest.approx(dist, abs=1e-5) == 50.0
    assert tcpa < 0.0    # Já estão a afastar-se
    assert estado == "A Afastar-se"
    assert risco == "SEGURO"

def test_dcpa_tcpa_paralelos():
    """Dois robôs paralelos com a mesma velocidade."""
    pA = (0.0, 0.0)
    vA = (2.0, 0.0)
    
    pB = (0.0, 30.0)
    vB = (2.0, 0.0)

    dist, dcpa, tcpa, estado, risco = calcular_dcpa_tcpa(pA, vA, pB, vB)

    assert pytest.approx(dist, abs=1e-5) == 30.0
    assert pytest.approx(dcpa, abs=1e-5) == 30.0
    assert estado == "Paralelo / Estacionário"
    assert risco == "SEGURO"
