"""
Esquema de validação do config.yaml (Pydantic).
Os campos opcionais têm valores por omissão, por isso um config.yaml antigo continua válido.
"""

from pathlib import Path
from typing import List, Literal, Optional

import yaml
from pydantic import BaseModel, Field

PASTA_PROJETO = Path(__file__).resolve().parents[1]
CAMINHO_OMISSAO = PASTA_PROJETO / 'config' / 'config.yaml'

CAMPOS_SAIDA = ['heading', 'velocidade_ms', 'distancia_origem_m']


class ReferenciaSuperficie(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude geodésica em graus")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude geodésica em graus")
    alt: float = Field(..., description="Altura elipsoidal WGS84 em metros (≈ nível do mar + ondulação do geoide)")


class RoboConfig(BaseModel):
    id: str = Field(..., description="Identificador único do robô")
    ficheiro_csv: str = Field(..., description="CSV de telemetria (relativo à pasta do projeto)")
    cor: str = Field(..., description="Código de cor hexadecimal para renderização")
    # Os logs desta missão têm frame_id 'world_ned' (yaw já é o heading); 'enu' é para logs ROS em ENU
    convencao_orientacao: Literal['ned', 'enu'] = Field('ned', description="Referencial do quaternion")


class ConfigReamostragem(BaseModel):
    passo_s: float = Field(1.0, gt=0, description="Passo da grelha temporal comum (s)")
    falha_max_s: float = Field(5.0, gt=0, description="Falhas maiores do que isto não são interpoladas (s)")


class ConfigAnomalias(BaseModel):
    limiar_salto_ms: float = Field(10.0, gt=0, description="Velocidade aparente acima da qual há salto de GPS (m/s)")
    dropout_min_s: float = Field(2.0, gt=0, description="Intervalo entre amostras considerado falha de dados (s)")
    limiar_aceleracao_ms2: float = Field(1.0, gt=0, description="Aceleração considerada anómala (m/s²)")


class ConfigSaida(BaseModel):
    campos: List[Literal['heading', 'velocidade_ms', 'distancia_origem_m']] = Field(default_factory=lambda: list(CAMPOS_SAIDA))
    referencial: Literal['ned', 'lla', 'ambos'] = Field('ambos', description="Coordenadas a exportar")
    taxa_hz: float = Field(1.0, gt=0, description="Amostras por segundo no CSV exportado")
    intervalo_s: Optional[List[float]] = Field(None, min_length=2, max_length=2, description="[início, fim] em s de missão; vazio = missão toda")


class ConfigMapa(BaseModel):
    offline: Literal['auto', 'sim', 'nao'] = Field('auto', description="'auto' testa a ligação à internet no arranque")


class ConfigIA(BaseModel):
    ativo: bool = Field(True, description="Se False, usa sempre o texto por regras")
    fornecedor: Literal['ollama', 'api'] = Field('ollama', description="'ollama' (local) ou 'api' (externa, com chave)")
    url: str = Field("http://localhost:11434", description="Endereço da API local do Ollama")
    modelo: str = Field("qwen2.5:3b", description="Nome do modelo instalado com 'ollama pull'")
    timeout_s: float = Field(60.0, gt=0, description="Tempo máximo de espera pela resposta (s)")
    cache: bool = Field(True, description="Guarda a resposta por instante para não repetir pedidos")
    api_url: str = Field("https://api.openai.com/v1", description="Endereço base de uma API compatível com /chat/completions")
    api_modelo: str = Field("gpt-4o-mini", description="Modelo da API externa")
    chave_env: str = Field("OPENAI_API_KEY", description="Variável de ambiente com a chave da API (a chave nunca vai no YAML)")


class ConfiguracaoMissao(BaseModel):
    referencia_superficie: ReferenciaSuperficie
    robos: List[RoboConfig]
    reamostragem: ConfigReamostragem = ConfigReamostragem()
    anomalias: ConfigAnomalias = ConfigAnomalias()
    saida: ConfigSaida = ConfigSaida()
    mapa: ConfigMapa = ConfigMapa()
    ia: ConfigIA = ConfigIA()


def carregar_configuracao(caminho=CAMINHO_OMISSAO):
    """Lê o YAML e valida-o; um campo em falta ou inválido dá logo um erro claro."""
    with open(caminho, 'r', encoding='utf-8') as ficheiro:
        dados_brutos = yaml.safe_load(ficheiro)
    return ConfiguracaoMissao(**dados_brutos).model_dump()
