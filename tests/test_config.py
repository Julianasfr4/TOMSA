"""
Testes unitários de validação da configuração e ficheiros CSV (TOMSA 2026)
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.esquema import carregar_configuracao, ConfiguracaoMissao, CAMINHO_OMISSAO, PASTA_PROJETO


def test_carregar_configuracao_valida():
    """O ficheiro config/config.yaml deve existir e cumprir o esquema Pydantic."""
    assert CAMINHO_OMISSAO.exists(), "Ficheiro config/config.yaml não encontrado!"

    config = carregar_configuracao()
    assert "referencia_superficie" in config
    assert "robos" in config
    assert len(config["robos"]) >= 1
    assert config["saida"]["referencial"] in ("ned", "lla", "ambos")


def test_existencia_ficheiros_csv():
    """Todos os ficheiros CSV listados no config.yaml devem existir no disco."""
    config = carregar_configuracao()
    for robo in config["robos"]:
        caminho_csv = PASTA_PROJETO / robo["ficheiro_csv"]
        assert caminho_csv.exists(), f"Ficheiro de dados '{caminho_csv}' não existe!"


def test_validacao_pydantic_valores_invalidos():
    """Pydantic deve lançar erro se a latitude/longitude for fisicamente impossível."""
    from pydantic import ValidationError

    dados_invalidos = {
        "referencia_superficie": {
            "lat": 999.0,  # Latitude impossível (> 90°)
            "lon": -8.813,
            "alt": 55.0
        },
        "robos": []
    }

    with pytest.raises(ValidationError):
        ConfiguracaoMissao(**dados_invalidos)


def test_valores_por_omissao():
    """Secções opcionais em falta recebem os valores por omissão."""
    config = ConfiguracaoMissao(referencia_superficie={"lat": 41.45, "lon": -8.81, "alt": 55.0}, robos=[]).model_dump()
    assert config["reamostragem"]["falha_max_s"] == 5.0
    assert config["saida"]["referencial"] == "ambos"
    assert config["saida"]["intervalo_s"] is None
    assert config["mapa"]["offline"] == "auto"
    assert config["ia"]["cache"] is True


def test_saida_invalida():
    """Referencial desconhecido ou intervalo com mais de dois valores são rejeitados."""
    from pydantic import ValidationError
    base = {"referencia_superficie": {"lat": 41.45, "lon": -8.81, "alt": 55.0}, "robos": []}
    with pytest.raises(ValidationError):
        ConfiguracaoMissao(**base, saida={"referencial": "enu"})
    with pytest.raises(ValidationError):
        ConfiguracaoMissao(**base, saida={"intervalo_s": [0, 10, 20]})
