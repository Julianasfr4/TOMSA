"""
Leitura em voz alta da explicação, gerada no servidor com o espeak-ng.
Funciona sem internet e em qualquer browser (o áudio chega como um ficheiro WAV).
Instalação no Linux: sudo apt install espeak-ng
"""

import base64
import re
import shutil
import subprocess

VOZ = 'pt'              # português de Portugal no espeak-ng ('pt-br' = Brasil)
PALAVRAS_POR_MINUTO = 150


def texto_para_fala(texto_markdown):
    """Tira as linhas em itálico (notas como 'Gerado pelo modelo...') e a formatação Markdown."""
    linhas = [l for l in str(texto_markdown).splitlines()
              if not re.fullmatch(r'\*[^*].*\*', l.strip())]
    return re.sub(r'[*#`]', '', ' '.join(linhas)).replace('_', ' ').strip()   # robo_1 -> robo 1


def sintetizar_wav(texto, voz=VOZ):
    """Devolve o áudio WAV (bytes). Lança FileNotFoundError se o espeak-ng não estiver instalado."""
    programa = shutil.which('espeak-ng') or shutil.which('espeak')
    if programa is None:
        raise FileNotFoundError("espeak-ng não instalado")
    resultado = subprocess.run(
        [programa, '-v', voz, '-s', str(PALAVRAS_POR_MINUTO), '--stdout', texto],
        capture_output=True, timeout=60, check=True
    )
    return resultado.stdout


def audio_da_explicacao(texto_markdown):
    """Devolve (src_para_html_Audio, aviso). Um dos dois vem vazio."""
    texto = texto_para_fala(texto_markdown)
    if not texto:
        return '', "Ainda não há explicação para ler."
    try:
        wav = sintetizar_wav(texto)
    except FileNotFoundError:
        return '', "Para ouvir, instala o espeak-ng: sudo apt install espeak-ng"
    except (subprocess.SubprocessError, OSError) as erro:
        return '', f"Não foi possível gerar o áudio ({type(erro).__name__})."
    return 'data:audio/wav;base64,' + base64.b64encode(wav).decode('ascii'), ''
