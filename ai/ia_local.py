"""
TOMSA 2026 - Copiloto de IA (Ollama local ou API externa)

O Python calcula primeiro os factos do instante (posições, AER, DCPA/TCPA, anomalias GPS)
e só envia ao modelo de linguagem um resumo estruturado em JSON. O modelo limita-se a
redigir a explicação em português. O fornecedor escolhe-se no config.yaml:
  - 'ollama': modelo local, sem chave nem internet;
  - 'api': API externa compatível com /chat/completions (OpenAI, Groq, Mistral, ...),
    com a chave lida de uma variável de ambiente (nunca escrita no YAML).
Se o modelo não responder, usa-se um texto por regras construído a partir dos mesmos factos.
"""

import json
import os
import datetime
import urllib.request
import urllib.error

from analysis.risco import calcular_dcpa_tcpa, velocidade_ned
from geo.transformacoes import ned_para_aer
from io_dados.leitor import estado_no_instante

CONFIG_IA_OMISSAO = {
    'ativo': True,
    'fornecedor': 'ollama',
    'url': 'http://localhost:11434',
    'modelo': 'qwen2.5:3b',
    'timeout_s': 60,
    'cache': True,
    'api_url': 'https://api.openai.com/v1',
    'api_modelo': 'gpt-4o-mini',
    'chave_env': 'OPENAI_API_KEY',
}

# Respostas já obtidas do modelo, por (instante, robô de referência, modelo)
_cache_respostas = {}

CARDINAIS = ['Norte', 'Nordeste', 'Este', 'Sudeste', 'Sul', 'Sudoeste', 'Oeste', 'Noroeste']


def factos_missao(dados_robos, tempo_atual, ego_robo, anomalias_conhecidas):
    """
    Reúne num dicionário (serializável em JSON) todos os factos numéricos do instante,
    vistos a partir do robô de referência. Devolve None se o robô de referência não tiver dados.
    """
    t = int(tempo_atual)
    ego = estado_no_instante(dados_robos[ego_robo], t)
    if ego is None:
        return None

    hora = datetime.datetime.fromtimestamp(ego['tempo_real_unix'], datetime.timezone.utc)
    factos = {
        'instante': {'t_missao_s': t, 'hora_utc': hora.strftime('%H:%M:%S')},
        'robo_referencia': {
            'id': ego_robo,
            'velocidade_ms': round(float(ego['velocidade_ms']), 2),
            'heading_graus': round(float(ego['heading']), 0),
            'rumo_cardinal': CARDINAIS[int(((ego['heading'] + 22.5) % 360) / 45)],
            'profundidade_m': round(float(ego['D_metros']), 1),
            'situacao_vertical': descrever_profundidade(float(ego['D_metros'])),
            'distancia_origem_m': round(float(ego['distancia_origem_m']), 1),
        },
        'vizinhos': [],
        'robos_sem_dados': [],
        'anomalias_gps_proximas': [],
    }

    for rid, df in dados_robos.items():
        if rid == ego_robo:
            continue
        viz = estado_no_instante(df, t)
        if viz is None:
            factos['robos_sem_dados'].append(rid)
            continue

        dn = viz['N_metros'] - ego['N_metros']
        de = viz['E_metros'] - ego['E_metros']
        dd = viz['D_metros'] - ego['D_metros']
        dist, dcpa, tcpa, estado, risco = calcular_dcpa_tcpa(
            (ego['N_metros'], ego['E_metros']), velocidade_ned(ego),
            (viz['N_metros'], viz['E_metros']), velocidade_ned(viz)
        )
        azimute, _, distancia = ned_para_aer(dn, de, dd)
        factos['vizinhos'].append({
            'id': rid,
            'distancia_3d_m': round(float(distancia), 1),
            'azimute_graus': round(float(azimute), 0),
            'diferenca_profundidade_m': round(float(dd), 1),
            'dcpa_m': round(dcpa, 1),
            'tcpa_s': round(tcpa, 0) if tcpa >= 0 else None,
            'dinamica': estado,
            'risco': risco,
        })

    # Do mais próximo para o mais afastado, para o modelo não ter de comparar distâncias
    factos['vizinhos'].sort(key=lambda v: v['distancia_3d_m'])

    for a in anomalias_conhecidas:
        if abs(a['tempo_s'] - t) <= 45:
            factos['anomalias_gps_proximas'].append(
                {'robo': a['robo'], 'hora_utc': a['hora_utc'], 'velocidade_aparente_ms': a['vel_salto']}
            )

    return factos


def descrever_profundidade(d_metros):
    """D é positivo para baixo; perto de 0 ou negativo (ruído da altitude GPS) o robô está à superfície."""
    if d_metros <= 0.5:
        return "à superfície"
    return f"a {d_metros:.1f} m de profundidade"


def texto_por_regras(factos):
    """Narrativa determinística (sem modelo de linguagem) a partir dos mesmos factos."""
    ego = factos['robo_referencia']
    paragrafos = [
        f"**{factos['instante']['hora_utc']} UTC (t = {factos['instante']['t_missao_s']} s).** "
        f"O **{ego['id']}** segue a {ego['velocidade_ms']:.2f} m/s com rumo {ego['heading_graus']:.0f}° ({ego['rumo_cardinal']}), "
        f"{descrever_profundidade(ego['profundidade_m'])} e a {ego['distancia_origem_m']:.1f} m da origem NED."
    ]
    frases = []
    for v in factos['vizinhos']:
        if v['risco'] == 'CRÍTICO':
            frases.append(f"Alerta: o **{v['id']}** está a {v['distancia_3d_m']:.1f} m (azimute {v['azimute_graus']:.0f}°) "
                          f"e a aproximar-se, devendo ficar a {v['dcpa_m']:.1f} m dentro de {v['tcpa_s']:.0f} s.")
        elif v['dinamica'] == 'A Convergir':
            frases.append(f"O **{v['id']}** está a {v['distancia_3d_m']:.1f} m (azimute {v['azimute_graus']:.0f}°) e a aproximar-se, "
                          f"mas com passagem segura (distância mínima prevista de {v['dcpa_m']:.1f} m).")
        else:
            frases.append(f"O **{v['id']}** está a {v['distancia_3d_m']:.1f} m (azimute {v['azimute_graus']:.0f}°) e a afastar-se.")
    if factos['robos_sem_dados']:
        frases.append(f"Sem dados neste instante: {', '.join(factos['robos_sem_dados'])}.")
    if frases:
        paragrafos.append(" ".join(frases))
    if factos['anomalias_gps_proximas']:
        a = factos['anomalias_gps_proximas'][0]
        paragrafos.append(f"Foi detetado um salto de GPS no **{a['robo']}** às {a['hora_utc']} "
                          f"({a['velocidade_aparente_ms']} m/s aparentes).")
    return "\n\n".join(paragrafos)


def construir_prompt(factos):
    """
    Instruções + rascunho por regras. Um modelo pequeno (3B) inventa e contradiz-se quando redige
    a partir do JSON dos factos, por isso pede-se apenas que reescreva o rascunho, que já está correto.
    """
    if factos['anomalias_gps_proximas']:
        regra_gps = "- Menciona a anomalia de GPS numa frase.\n"
    else:
        regra_gps = "- Não há anomalias de GPS neste instante: não fales de GPS.\n"
    return (
        "És o copiloto de uma missão de robôs marinhos (subaquáticos) na costa da Aguçadoura, Portugal.\n"
        "Reescreve o RASCUNHO abaixo para um operador, em português de Portugal, de forma clara e natural.\n"
        "Regras:\n"
        "- Mantém todos os números, robôs e conclusões do rascunho; não acrescentes factos nem tires conclusões novas.\n"
        "- Se um vizinho está 'a afastar-se' ou 'a aproximar-se', mantém exatamente isso.\n"
        "- Podes explicar que DCPA é a distância mínima prevista entre dois robôs e TCPA o tempo até lá.\n"
        + regra_gps +
        "- Dois parágrafos curtos, no máximo 120 palavras, sem listas, sem saudações nem títulos.\n"
        "- Português europeu (ex.: 'o seu', 'a navegar'), nunca português do Brasil.\n"
        "- Não copies o rascunho palavra por palavra: escreve frases corridas, como quem explica a um colega.\n"
        "- Responde só com o texto final, sem repetir estas instruções nem o rascunho.\n\n"
        f"RASCUNHO:\n{texto_por_regras(factos).replace('**', '')}\n"
    )


def pedir_ollama(prompt, config_ia):
    """Chama a API HTTP local do Ollama (/api/generate, sem streaming). Lança exceção em caso de falha."""
    corpo = json.dumps({
        'model': config_ia['modelo'],
        'prompt': prompt,
        'stream': False,
        'options': {'temperature': 0.2},
    }).encode('utf-8')
    pedido = urllib.request.Request(
        config_ia['url'].rstrip('/') + '/api/generate',
        data=corpo, headers={'Content-Type': 'application/json'}, method='POST'
    )
    with urllib.request.urlopen(pedido, timeout=config_ia['timeout_s']) as resposta:
        texto = json.loads(resposta.read().decode('utf-8')).get('response', '').strip()
    if not texto:
        raise ValueError("O Ollama devolveu uma resposta vazia")
    return texto


def pedir_api(prompt, config_ia):
    """Chama uma API externa no formato /chat/completions. A chave vem da variável de ambiente indicada."""
    chave_api = os.environ.get(config_ia['chave_env'])
    if not chave_api:
        raise ValueError(f"variável de ambiente {config_ia['chave_env']} não definida")
    corpo = json.dumps({
        'model': config_ia['api_modelo'],
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.2,
    }).encode('utf-8')
    pedido = urllib.request.Request(
        config_ia['api_url'].rstrip('/') + '/chat/completions',
        data=corpo, method='POST',
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {chave_api}'}
    )
    with urllib.request.urlopen(pedido, timeout=config_ia['timeout_s']) as resposta:
        dados = json.loads(resposta.read().decode('utf-8'))
    try:
        texto = dados['choices'][0]['message']['content'].strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ValueError("A API devolveu uma resposta num formato inesperado")
    if not texto:
        raise ValueError("A API devolveu uma resposta vazia")
    return texto


def explicar_situacao(dados_robos, tempo_atual, ego_robo, anomalias_conhecidas, config_ia=None):
    """
    Devolve (texto_markdown, origem), em que origem é 'ollama', 'api', 'cache' ou 'regras'.
    Nunca lança exceção: qualquer falha do modelo cai na narrativa por regras.
    """
    config_ia = {**CONFIG_IA_OMISSAO, **(config_ia or {})}
    factos = factos_missao(dados_robos, tempo_atual, ego_robo, anomalias_conhecidas)
    if factos is None:
        return f"O {ego_robo} não tem dados neste instante (ainda não começou ou o log já terminou).", 'regras'

    texto_regras = texto_por_regras(factos)
    if not config_ia['ativo']:
        return texto_regras, 'regras'

    usar_api = config_ia['fornecedor'] == 'api'
    modelo = config_ia['api_modelo'] if usar_api else config_ia['modelo']
    nome_fornecedor = 'API externa' if usar_api else 'Ollama'

    chave = (int(tempo_atual), ego_robo, modelo)
    if config_ia['cache'] and chave in _cache_respostas:
        return _cache_respostas[chave], 'cache'

    try:
        prompt = construir_prompt(factos)
        texto = pedir_api(prompt, config_ia) if usar_api else pedir_ollama(prompt, config_ia)
        texto = f"{texto}\n\n*Gerado pelo modelo {modelo} ({nome_fornecedor}) a partir dos factos calculados.*"
        if config_ia['cache']:
            _cache_respostas[chave] = texto
        return texto, 'api' if usar_api else 'ollama'
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError, json.JSONDecodeError) as erro:
        if usar_api:
            ajuda = f"confirma a variável de ambiente {config_ia['chave_env']} e o api_url no config.yaml"
        else:
            ajuda = f"confirma que o Ollama está a correr em {config_ia['url']} e que o modelo {modelo} foi descarregado"
        aviso = (f"*{nome_fornecedor} indisponível ({type(erro).__name__}: {erro}); texto gerado por regras. "
                 f"Para usar o modelo, {ajuda}.*")
        return f"{texto_regras}\n\n{aviso}", 'regras'
