"""
Saídas do dashboard (requisito 5): CSV de telemetria configurado pela secção 'saida'
do config.yaml e relatório de missão em texto.
"""

import datetime

import pandas as pd

from io_dados.leitor import estado_no_instante

COLUNAS_REFERENCIAL = {
    'ned': ['N_metros', 'E_metros', 'D_metros'],
    'lla': ['lat', 'lon', 'alt'],
}


def _utc(timestamp_unix, formato='%Y-%m-%d %H:%M:%S UTC'):
    return datetime.datetime.fromtimestamp(timestamp_unix, datetime.timezone.utc).strftime(formato)


def tabela_telemetria(dados_grelha, cfg_saida, passo_s):
    """
    Telemetria de todos os robôs na grelha comum, filtrada pela configuração de saída:
    - intervalo_s: [início, fim] em segundos de missão (None = missão toda)
    - taxa_hz: amostras por segundo (subamostragem da grelha, no máximo 1/passo_s)
    - referencial: 'ned', 'lla' ou 'ambos'
    - campos: colunas adicionais (heading, velocidade_ms, distancia_origem_m)
    """
    salto = max(1, int(round(1.0 / (cfg_saida['taxa_hz'] * passo_s))))
    referenciais = ['ned', 'lla'] if cfg_saida['referencial'] == 'ambos' else [cfg_saida['referencial']]
    colunas = [c for r in referenciais for c in COLUNAS_REFERENCIAL[r]] + list(cfg_saida['campos'])

    partes = []
    for id_robo, df in dados_grelha.items():
        sub = df.iloc[::salto]
        if cfg_saida['intervalo_s'] is not None:
            ini, fim = cfg_saida['intervalo_s']
            sub = sub[(sub['tempo_segundos'] >= ini) & (sub['tempo_segundos'] <= fim)]
        sub = sub.dropna(subset=['N_metros'])
        partes.append(pd.DataFrame({
            'robo': id_robo,
            'tempo_s': sub['tempo_segundos'].round(2).values,
            'hora_utc': [_utc(t) for t in sub['timestamp_unix']],
            **{c: sub[c].round(7 if c in ('lat', 'lon') else 3).values for c in colunas},
        }))
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def relatorio_missao(dados_grelha, config, tempo, hora_real, resumo):
    """Relatório em texto do instante selecionado e da missão completa."""
    origem = config['referencia_superficie']
    linhas = [
        "=" * 80,
        "TOMSA 2026 - RELATÓRIO DE MISSÃO",
        "=" * 80,
        f"Data/Hora de Exportação: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Instante da Missão Selecionado: {tempo} s ({datetime.timedelta(seconds=int(tempo))})",
        f"Hora Real da Missão: {hora_real}",
        "",
        "REFERÊNCIA DE SUPERFÍCIE (ORIGEM NED):",
        f"  - Latitude:  {origem['lat']:.8f}°",
        f"  - Longitude: {origem['lon']:.8f}°",
        f"  - Altitude:  {origem['alt']:.2f} m (elipsoidal WGS84)",
        "",
        "ESTADO DOS ROBÔS NO INSTANTE SELECIONADO:",
    ]
    for id_r, df in dados_grelha.items():
        ult = estado_no_instante(df, tempo)
        if ult is not None:
            linhas.append(
                f"  [{id_r}] Pos NED: (N: {ult['N_metros']:7.1f}m, E: {ult['E_metros']:7.1f}m, D: {ult['D_metros']:6.2f}m) | "
                f"Heading: {ult['heading']:5.1f}° | Vel: {ult['velocidade_ms']:4.2f} m/s | Dist. Origem: {ult['distancia_origem_m']:6.1f}m"
            )
        else:
            linhas.append(f"  [{id_r}] Sem telemetria disponível neste instante.")

    linhas += ["", "MISSÃO COMPLETA:"]
    for id_r, df in dados_grelha.items():
        ativo = df.dropna(subset=['N_metros'])
        linhas.append(
            f"  - {id_r}: ativo de t={ativo['tempo_segundos'].iloc[0]:.0f}s a t={ativo['tempo_segundos'].iloc[-1]:.0f}s, "
            f"Vel. Média = {ativo['velocidade_ms'].mean():.2f} m/s, Vel. Máxima = {ativo['velocidade_ms'].max():.2f} m/s"
        )
    for p in resumo['distancias_minimas']:
        if p['distancia_m'] is not None:
            linhas.append(f"  - Distância mínima {p['par'][0]} ↔ {p['par'][1]}: {p['distancia_m']:.1f} m (t={p['tempo_s']:.0f}s)")
    linhas.append(f"  - Saltos de GPS: {len(resumo['saltos_gps'])} | Falhas de dados: {len(resumo['dropouts'])} | "
                  f"Alertas de proximidade (< 20 m): {len(resumo['alertas_proximidade'])}")
    linhas.append("=" * 80)
    return "\n".join(linhas)
