"""
Testes do copiloto de IA local (TOMSA 2026): factos, prompt, chamada HTTP ao Ollama e fallback por regras.
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ai import ia_local


def _robo(n0, e0, heading, vel, t_ini=0.0, t_fim=100.0):
    """Robô sintético em linha reta, amostrado a 1 Hz."""
    tempos = [float(t) for t in range(int(t_ini), int(t_fim) + 1)]
    return pd.DataFrame({
        'tempo_segundos': tempos,
        'tempo_real_unix': [1760095800.0 + t for t in tempos],
        'N_metros': [n0] * len(tempos), 'E_metros': [e0] * len(tempos), 'D_metros': [5.0] * len(tempos),
        'heading': [heading] * len(tempos), 'velocidade_ms': [vel] * len(tempos),
        'distancia_origem_m': [(n0**2 + e0**2) ** 0.5] * len(tempos),
    })


@pytest.fixture
def dados():
    return {
        'robo_1': _robo(0.0, 0.0, 0.0, 1.0),                   # a Norte, 1 m/s
        'robo_4': _robo(50.0, 0.0, 180.0, 1.0),                # 50 m a Norte, de frente
        'robo_7': _robo(0.0, 300.0, 90.0, 0.5, t_ini=200, t_fim=300),  # ainda não começou
    }


def test_factos_missao(dados):
    f = ia_local.factos_missao(dados, 10, 'robo_1', [])
    assert f['robo_referencia']['id'] == 'robo_1'
    assert f['robos_sem_dados'] == ['robo_7']
    viz = f['vizinhos'][0]
    assert viz['id'] == 'robo_4'
    assert viz['dcpa_m'] == pytest.approx(0.0, abs=1e-6)   # rota de colisão frontal
    assert viz['tcpa_s'] == pytest.approx(25.0)            # 50 m / 2 m/s
    assert viz['risco'] == 'CRÍTICO'
    json.dumps(f)  # tem de ser serializável


def test_prompt_contem_factos(dados):
    prompt = ia_local.construir_prompt(ia_local.factos_missao(dados, 10, 'robo_1', []))
    assert 'português de Portugal' in prompt
    assert 'robo_4' in prompt and 'Alerta' in prompt   # o rascunho por regras destaca o risco CRÍTICO


def test_fallback_quando_ollama_indisponivel(dados):
    config = {'url': 'http://127.0.0.1:9', 'timeout_s': 1}   # porta sem servidor
    texto, origem = ia_local.explicar_situacao(dados, 10, 'robo_1', [], config)
    assert origem == 'regras'
    assert 'Ollama indisponível' in texto and 'robo_1' in texto


def test_ia_desativada_usa_regras(dados):
    texto, origem = ia_local.explicar_situacao(dados, 10, 'robo_1', [], {'ativo': False})
    assert origem == 'regras'


def test_resposta_do_ollama(dados):
    """Servidor HTTP falso com a mesma API do Ollama (/api/generate)."""
    recebido = {}

    class FalsoOllama(BaseHTTPRequestHandler):
        def do_POST(self):
            recebido['corpo'] = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            resposta = json.dumps({'response': 'O robo_1 segue para Norte.'}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(resposta)

        def log_message(self, *args):
            pass

    servidor = HTTPServer(('127.0.0.1', 0), FalsoOllama)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        config = {'url': f'http://127.0.0.1:{servidor.server_port}', 'modelo': 'teste', 'timeout_s': 5}
        texto, origem = ia_local.explicar_situacao(dados, 10, 'robo_1', [], config)
    finally:
        servidor.shutdown()

    assert origem == 'ollama'
    assert texto.startswith('O robo_1 segue para Norte.')
    assert recebido['corpo']['model'] == 'teste' and recebido['corpo']['stream'] is False


def test_cache_por_instante(dados):
    """A segunda pergunta no mesmo instante não volta a chamar o Ollama."""
    chamadas = []

    class FalsoOllama(BaseHTTPRequestHandler):
        def do_POST(self):
            chamadas.append(1)
            self.rfile.read(int(self.headers['Content-Length']))
            resposta = json.dumps({'response': 'Resposta guardada.'}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(resposta)

        def log_message(self, *args):
            pass

    ia_local._cache_respostas.clear()
    servidor = HTTPServer(('127.0.0.1', 0), FalsoOllama)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        config = {'url': f'http://127.0.0.1:{servidor.server_port}', 'modelo': 'cache-teste', 'timeout_s': 5}
        _, origem1 = ia_local.explicar_situacao(dados, 20, 'robo_1', [], config)
        texto2, origem2 = ia_local.explicar_situacao(dados, 20, 'robo_1', [], config)
        _, origem3 = ia_local.explicar_situacao(dados, 21, 'robo_1', [], config)
    finally:
        servidor.shutdown()

    assert (origem1, origem2, origem3) == ('ollama', 'cache', 'ollama')
    assert texto2.startswith('Resposta guardada.')
    assert len(chamadas) == 2


def test_resposta_da_api_externa(dados, monkeypatch):
    """Servidor falso no formato /chat/completions; a chave vem da variável de ambiente."""
    recebido = {}

    class FalsaAPI(BaseHTTPRequestHandler):
        def do_POST(self):
            recebido['caminho'] = self.path
            recebido['autorizacao'] = self.headers['Authorization']
            recebido['corpo'] = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            resposta = json.dumps({'choices': [{'message': {'content': 'O robo_4 aproxima-se.'}}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(resposta)

        def log_message(self, *args):
            pass

    monkeypatch.setenv('TOMSA_CHAVE_TESTE', 'segredo123')
    ia_local._cache_respostas.clear()
    servidor = HTTPServer(('127.0.0.1', 0), FalsaAPI)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        config = {'fornecedor': 'api', 'api_url': f'http://127.0.0.1:{servidor.server_port}/v1',
                  'api_modelo': 'modelo-teste', 'chave_env': 'TOMSA_CHAVE_TESTE', 'timeout_s': 5}
        texto, origem = ia_local.explicar_situacao(dados, 10, 'robo_1', [], config)
    finally:
        servidor.shutdown()

    assert origem == 'api'
    assert texto.startswith('O robo_4 aproxima-se.') and 'API externa' in texto
    assert recebido['caminho'] == '/v1/chat/completions'
    assert recebido['autorizacao'] == 'Bearer segredo123'
    assert recebido['corpo']['model'] == 'modelo-teste'


def test_api_sem_chave_usa_regras(dados, monkeypatch):
    monkeypatch.delenv('TOMSA_CHAVE_INEXISTENTE', raising=False)
    config = {'fornecedor': 'api', 'chave_env': 'TOMSA_CHAVE_INEXISTENTE', 'api_modelo': 'sem-chave'}
    texto, origem = ia_local.explicar_situacao(dados, 10, 'robo_1', [], config)
    assert origem == 'regras'
    assert 'API externa indisponível' in texto


def test_texto_para_fala():
    from ai.voz import texto_para_fala
    texto = "O **robo_1** segue para Norte.\n\n*Gerado pelo modelo x (Ollama) a partir dos factos calculados.*"
    assert texto_para_fala(texto) == "O robo 1 segue para Norte."


def test_audio_sem_espeak(monkeypatch):
    from ai import voz
    monkeypatch.setattr(voz.shutil, 'which', lambda nome: None)
    src, aviso = voz.audio_da_explicacao("Olá")
    assert src == '' and 'espeak-ng' in aviso


@pytest.mark.skipif(__import__('shutil').which('espeak-ng') is None, reason="espeak-ng não instalado")
def test_audio_com_espeak():
    from ai.voz import audio_da_explicacao
    src, aviso = audio_da_explicacao("O robo_1 segue para Norte.")
    assert aviso == '' and src.startswith('data:audio/wav;base64,UklGR')   # 'RIFF' em base64
