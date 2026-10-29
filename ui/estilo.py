"""
Estilo comum a toda a página: cores, cartões e botões.
"""

from dash import html

COR_FUNDO = '#f5f6f8'
COR_CARTAO = '#ffffff'
COR_BORDA = '#dfe3e8'
COR_TEXTO = '#1f2328'
COR_SUAVE = '#5b6470'
COR_DESTAQUE = '#0b5cad'
CORES_RISCO = {'SEGURO': '#2e7d32', 'MODERADO': '#5b6470', 'ATENÇÃO': '#b26a00', 'CRÍTICO': '#c62828'}

ESTILO_CARTAO = {
    'backgroundColor': COR_CARTAO, 'border': f'1px solid {COR_BORDA}',
    'borderRadius': '8px', 'padding': '16px', 'marginBottom': '16px'
}
ESTILO_TITULO = {'margin': '0 0 12px 0', 'fontSize': '16px', 'fontWeight': '600'}
ESTILO_SUBTITULO = {'margin': '0 0 8px 0', 'fontSize': '13px', 'fontWeight': '600', 'color': COR_SUAVE}
ESTILO_CAIXA_TEXTO = {
    'backgroundColor': COR_FUNDO, 'border': f'1px solid {COR_BORDA}', 'borderRadius': '6px',
    'padding': '10px', 'fontFamily': 'monospace', 'fontSize': '12px', 'lineHeight': '1.5',
    'maxHeight': '140px', 'overflowY': 'auto', 'whiteSpace': 'pre-wrap'
}


def botao(texto, id_botao, principal=False):
    return html.Button(texto, id=id_botao, n_clicks=0, style={
        'backgroundColor': COR_DESTAQUE if principal else COR_CARTAO,
        'color': 'white' if principal else COR_TEXTO,
        'border': f'1px solid {COR_DESTAQUE if principal else COR_BORDA}',
        'padding': '8px 14px', 'borderRadius': '6px', 'cursor': 'pointer',
        'fontSize': '13px', 'marginRight': '8px', 'marginBottom': '8px'
    })
