# Como executar o Dashboard TOMSA 2026 (Grupo 20)

Guia passo a passo para pôr a app a correr num computador novo.
Testado em Ubuntu com Python 3.12. Os comandos são para escrever num terminal.

---

## 0. O que é preciso ter

- **Python 3.10 ou mais recente** — confirmar com `python3 --version`
- **git** — confirmar com `git --version` (se faltar: `sudo apt install git`)
- **venv do Python** — se o passo 2 der erro: `sudo apt install python3-venv`
- Acesso ao repositório no GitHub (se for privado, pedir para ser adicionada como colaboradora)

---

## 1. Descarregar o projeto

```bash
git clone https://github.com/Julianasfr4/TOMSA.git
cd TOMSA
```

Os dados da missão (`robot1_s1.csv`, `robot4_s1.csv`, `robot7_s1.csv`) já vêm no repositório.

## 2. Criar o ambiente virtual (só da primeira vez)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

A instalação demora alguns minutos. No início da linha do terminal passa a aparecer `(venv)`.

## 3. Arrancar a app

```bash
source venv/bin/activate     # sempre que se abre um terminal novo
python app.py
```

Esperar pela mensagem `Dash is running on http://127.0.0.1:8050/` (cerca de 20 s, porque os dados
são preparados no arranque) e abrir no browser: **http://127.0.0.1:8050**

Para parar a app: `Ctrl + C` no terminal.

## 4. Confirmar que está tudo bem (opcional)

```bash
pytest
```

Devem passar os 46 testes.

---

## 5. (Opcional) Explicação por IA — botão *Explicar com IA*

Sem este passo a app funciona na mesma: o botão mostra um texto gerado por regras.
Para o texto ser escrito por um modelo de linguagem local (sem internet nem chave):

1. Instalar o Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
   (ou seguir as instruções em https://ollama.com/download)
2. Descarregar o modelo (cerca de 1,9 GB):
   ```bash
   ollama pull qwen2.5:3b
   ```
3. Garantir que o Ollama está a correr **antes** de arrancar a app.
   Normalmente o instalador deixa-o como serviço; se não estiver, abrir outro terminal e correr:
   ```bash
   ollama serve
   ```

Teste rápido: `curl http://localhost:11434/api/version` deve devolver a versão.
A primeira explicação demora ~25 s (o modelo é carregado); as seguintes ~10–15 s.

**Alternativa sem instalar nada (online):** usar a API da Groq. Criar uma chave gratuita em
https://console.groq.com/keys, pôr `fornecedor: "api"` em `config/config.yaml` e, no terminal onde se
arranca a app:
```bash
export GROQ_API_KEY="a-tua-chave"
python app.py
```
A chave nunca se escreve nos ficheiros do projeto.

## 6. (Opcional) Leitura em voz alta — botão *Ouvir*

```bash
sudo apt install espeak-ng
```

---

## Problemas frequentes

| Sintoma | Solução |
|---|---|
| `ModuleNotFoundError: No module named 'dash'` | Faltou ativar o ambiente: `source venv/bin/activate` |
| `Address already in use` / porta 8050 ocupada | Já há uma app a correr. Fechá-la (`Ctrl + C` nesse terminal) ou `pkill -f "python app.py"` |
| Mapa aparece sem fundo | Sem internet: o mapa funciona na mesma, só sem as imagens do OpenStreetMap |
| *Ollama indisponível (…); texto gerado por regras* | O Ollama não está a correr ou o modelo não foi descarregado — ver passo 5 |
| Botão *Ouvir* dá aviso | Falta o `espeak-ng` — ver passo 6 |

## Onde mexer

- **Configuração** (robôs, ficheiros CSV, cores, limiares, IA): `config/config.yaml`
- **Código da app**: `app.py` (arranque), `ui/` (layout e gráficos), `analysis/` (cálculos), `ai/` (IA e voz)
- Mais detalhes sobre as funcionalidades e a matemática: `README.md`
