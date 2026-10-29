# 🛰️ TOMSA 2026 — Multi-Robot Trajectory Replay & Coordinate Frame Visualizer

**ISEP — Instituto Superior de Engenharia do Porto**  
**Mestrado em Engenharia Eletrotécnica e de Computadores (Sistemas Autónomos)**  
**Unidade Curricular:** Tópicos de Matemática para Sistemas Autónomos (TOMSA 2026)  
**Grupo:** 20 (Juliana Rodrigues)  
**Docente:** Pedro Barbosa Guedes  

> ▶️ **Para executar a app num computador novo, seguir o guia passo a passo em [`COMO_EXECUTAR.md`](COMO_EXECUTAR.md).**

---

## 📌 Descrição Geral do Projeto

Este projeto consiste num **dashboard web interativo em Python/Dash** concebido para reproduzir missões marinhas reais a partir de *logs* de robôs marítimos no formato ROS (recolhidos na costa da Aguçadoura pelo INESC TEC), permitindo a visualização e análise matemática de trajetórias multi-robô em diferentes referenciais (Global WGS84/NED, Local do Corpo e AER).

---

## 🚀 Funcionalidades Implementadas

O projeto cumpre integralmente os **5 requisitos obrigatórios** do guião e as **extensões avançadas da Fase 5**:

### 1. 🌍 Visão Global (Requisito 1)
* Mapa interativo geográfico baseado em **MapLibre** com cartas náuticas do **OpenSeaMap** (sem dependência de chaves pagas do Mapbox).
* **Modo offline:** sem internet, o mapa usa um fundo branco sem mosaicos e a app continua a funcionar (opção `mapa.offline` no `config.yaml`: `auto`, `sim` ou `nao`).
* Representação simultânea das trajetórias históricas e das posições dinâmicas dos 3 robôs marinhos (`robo_1`, `robo_4`, `robo_7`), identificados pelas suas respetivas cores.
* Destaque para o ponto de referência inicial da missão (**Origem NED / Surface Reference**).

### 2. 🎯 Visão Local 3D & Coordenadas AER (Requisito 2)
* Seleção dinâmica do robô de referência (*ego*) através de um menu *dropdown*.
* Vista local em **3D** ou **2D (vista de cima)**, escolhida ao lado do robô de referência.
* O radar mostra o **percurso do próprio robô** e o dos vizinhos no referencial do corpo, com uma **seta de *heading*** a indicar a frente do robô.
* Projeção 3D do radar no **referencial do corpo** (*body frame* do robô: frente/trás, esquerda/direita e profundidade). A rotação escolhe-se ao lado: **só yaw** (rotação 2D pelo *heading*) ou **completa** (roll, pitch e yaw a partir do quaternion). O painel mostra também o roll e o pitch do robô.
* Painel de **Coordenadas AER** (*Azimuth-Elevation-Range*): cálculo em tempo real da distância linear 3D (*slant range*), azimute de bússola e elevação para todos os robôs vizinhos (implementação própria, validada contra o `ned2aer` do `pymap3d`).

### 2b. 🌊 Profundidade e velocidade
* Tabela com o estado atual dos 3 robôs (profundidade D, velocidade, rumo e distância à origem).
* Gráficos da profundidade e da velocidade de cada robô ao longo da missão, com uma linha que acompanha o instante do replay.
* **Validação da velocidade:** a velocidade do *twist* é comparada com a velocidade calculada a partir das posições (derivada numérica na grelha de 1 s, média móvel de 5 s), com o erro médio e mediano.
* Gráfico da **distância entre cada par de robôs** ao longo do tempo, com a linha de alerta de 20 m.

### 3. ⏱️ Mission Replay (Requisito 3)
* Linha do tempo interativa (*Slider*) com indicação de tempo relativo (segundos) e conversão para **hora real UTC** da missão a partir do *timestamp* Unix ROS.
* Caixa **"ir para"** para saltar para um instante exato (em segundos ou `h:mm:ss`).
* Botão de controlo de reprodução **Play / Pause** e seletor de velocidade (**1×, 5× e 10×** o tempo real; o relógio avança a cada 1 s).
* Os 3 robôs são **reamostrados numa grelha temporal comum** (1 s) com *t0* comum: posição interpolada linearmente e orientação por **SLERP** de quaternions. Falhas de dados maiores do que `falha_max_s` não são interpoladas.
* Otimização de desempenho com **`dash.Patch()`** para mover unicamente os marcadores sem redesenhar os gráficos nem sobrecarregar o browser.

### 4. ⚙️ Configuração Estruturada via YAML (Requisito 4)
* Parametrização integral através do ficheiro [`config/config.yaml`](config/config.yaml): origem de superfície (Latitude, Longitude, Altitude), identificadores dos robôs, caminhos dos CSV, cores, convenção da orientação (`ned`/`enu`), grelha de reamostragem, limiares de anomalias, saída, mapa e IA.
* **Validação rigorosa de esquema com Pydantic** (garante tipos válidos e limites geodésicos no arranque).

### 5. 📥 Registo de Missão & Exportação (Requisito 5: Output)
* **Exportação CSV:** Telemetria de todos os robôs na grelha comum, configurada pela secção `saida` do `config.yaml`: `campos` (heading, velocidade, distância à origem), `referencial` (`ned`, `lla` ou `ambos`), `taxa_hz` e `intervalo_s` (`[início, fim]` em segundos de missão, ou `null` para a missão toda).
* **Relatório TXT:** Relatório do instante selecionado e da missão completa (distâncias mínimas entre robôs e contagem de anomalias).
* **Exportação YAML:** Descarregamento da configuração ativa.
* **Log de Eventos em Tempo Real:** Monitorização cronológica de eventos e proximidade entre robôs.

### 6. 🧠 Mission Control & Análise de Risco (Extensão - Fase 5)
* **Avaliação de Risco de Colisão (DCPA / TCPA):** Cálculo vetorial analítico das normas internacionais de navegação marítima (COLREGs/IMO) para estimar a *Distance at Closest Point of Approach* e o *Time to Closest Point of Approach*.
* **Auditoria de Sensores (Saltos de GPS):** Deteção automática de anomalias de telemetria por diferenciação temporal da posição (identificando 3 saltos reais nos dados brutos com velocidades anómalas até $76\text{ m/s}$).
* **Falhas de dados e acelerações anómalas:** intervalos entre amostras acima de `dropout_min_s` e $|\Delta v/\Delta t|$ acima de `limiar_aceleracao_ms2`.
* **Distância mínima entre robôs:** para cada par, a menor distância 3D na missão e o instante em que ocorre.
* **Limpeza dos CSV:** linhas com valores em falta e *timestamps* duplicados são removidas no carregamento (o número removido aparece na consola).
* **Explicação por IA (Ollama local ou API externa):** o botão *Explicar com IA* envia ao modelo só os factos já calculados (posições, AER, DCPA/TCPA, anomalias) e o modelo redige o texto. O botão *Ouvir* lê a explicação em voz alta: o áudio é gerado no servidor com o `espeak-ng` (sem internet, em qualquer browser). O fornecedor escolhe-se em `ia.fornecedor` no `config.yaml`: `ollama` (local, sem chave) ou `api` (qualquer API compatível com `/chat/completions`, com a chave lida da variável de ambiente indicada em `ia.chave_env`). As respostas ficam em cache por instante. Se o modelo não responder, é mostrado um texto gerado por regras com os mesmos factos.

---

## 📐 Fundamentação Matemática e Referenciais

1. **ECEF e NED (North-East-Down):** Conversão LLA (WGS84) $\to$ ECEF $\to$ NED implementada em NumPy (`geo/transformacoes.py`), validada nos testes contra o `pymap3d` e o `pyproj` (erro < 1 mm):
   $$N(\varphi) = \frac{a}{\sqrt{1 - e^2 \sin^2\varphi}}, \quad \begin{bmatrix} x \\ y \\ z \end{bmatrix} = \begin{bmatrix} (N + h)\cos\varphi\cos\lambda \\ (N + h)\cos\varphi\sin\lambda \\ (N(1 - e^2) + h)\sin\varphi \end{bmatrix}, \quad \vec{p}_{\text{NED}} = R_{\text{NED}}(\varphi_0, \lambda_0)\,(\vec{p}_{\text{ECEF}} - \vec{p}_{0})$$
   A inversa usa $R_{\text{NED}}^T$ (matriz ortogonal) e o método iterativo para recuperar a latitude.
2. **Quaternions $\to$ Heading:** Yaw da sequência de Euler 'ZYX'. Os *logs* de `robo_1` e `robo_4` estão em `world_ned`, onde o yaw já é o heading de bússola ($0^\circ$ Norte, sentido horário). Para dados em ENU usa-se $\text{Heading} = (90^\circ - \text{Yaw}_{\text{ENU}}) \bmod 360^\circ$ (opção `convencao_orientacao`). Os testes confirmam que o heading coincide com o rumo real calculado a partir das posições.
3. **SLERP:** $\text{slerp}(q_0, q_1; u) = \frac{\sin((1-u)\theta)}{\sin\theta} q_0 + \frac{\sin(u\theta)}{\sin\theta} q_1$, que interpola a orientação sem o salto de $360^\circ \to 0^\circ$.
4. **Referencial do Corpo (Body Frame):** Rotação 2D das diferenças relativas de posição $(\Delta N, \Delta E)$:
   $$x_b = \Delta N \cos(\psi) + \Delta E \sin(\psi), \quad y_b = -\Delta N \sin(\psi) + \Delta E \cos(\psi), \quad z_b = -\Delta D$$
5. **Coordenadas AER (Azimuth - Elevation - Range):**
   $$\text{Range} = \sqrt{\Delta N^2 + \Delta E^2 + \Delta D^2}, \quad \text{Azimuth} = \text{atan2}(\Delta E, \Delta N) \pmod{360^\circ}$$
   Na rotação completa, o vetor relativo em NED é rodado pelo inverso da orientação do robô: $\vec{v}_b = R(q)^T\,\vec{v}_{\text{NED}}$ (referencial FRD; o eixo vertical do gráfico é $-z_b$).
6. **DCPA e TCPA (Álgebra Linear):**
   $$\tau_{\text{cpa}} = -\frac{\vec{p}_{\text{rel}} \cdot \vec{v}_{\text{rel}}}{\|\vec{v}_{\text{rel}}\|^2}, \quad \text{DCPA} = \|\vec{p}_{\text{rel}} + \vec{v}_{\text{rel}}\tau_{\text{cpa}}\|$$

7. **Velocidade a partir das posições:** $v = \sqrt{\dot N^2 + \dot E^2 + \dot D^2}$, com as derivadas por diferenças centrais (`np.gradient`) na grelha de 1 s.

---

## 🛠️ Instalação e Execução

### 1. Clonar e aceder ao repositório
```bash
git clone https://github.com/Julianasfr4/TOMSA.git
cd TOMSA
```

### 2. Criar e ativar o ambiente virtual
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar as dependências
```bash
pip install -r requirements.txt
```

### 4. (Opcional) Instalar o Ollama para a explicação por IA
Instalar a partir de https://ollama.com e descarregar o modelo indicado no `config.yaml`:
```bash
ollama pull qwen2.5:3b
```
Sem o Ollama a app funciona na mesma; a explicação passa a ser gerada por regras.

Para usar uma API externa em vez do Ollama, pôr `fornecedor: "api"` no `config/config.yaml` e definir a chave numa variável de ambiente antes de arrancar (a chave nunca é escrita no YAML):
```bash
export GROQ_API_KEY="a-tua-chave"   # chave criada em https://console.groq.com/keys
```

### (Opcional) Instalar a voz para o botão *Ouvir*
```bash
sudo apt install espeak-ng
```

### 5. Iniciar o Dashboard
```bash
python app.py
```
O modo de depuração do Dash está desligado. Para o ligar durante o desenvolvimento: `TOMSA_DEBUG=1 python app.py`.
Abrir o browser em: **`http://127.0.0.1:8050`**

### 6. Executar os Testes Unitários Automáticos
```bash
pytest
```
*(Executa os 46 testes: geodésia e AER contra pymap3d/pyproj, ida e volta LLA↔NED, ~111 km por grau de latitude, heading vs rumo real, rotação completa, SLERP, velocidade a partir das posições, falhas de dados, limpeza dos CSV, exportação, DCPA/TCPA, Pydantic, mapa offline e IA com servidores Ollama e API falsos).*

---

## 📂 Estrutura do Projeto

```text
TOMSA/
├── app.py                  # Arranque: carrega os dados, monta o layout e regista os callbacks
├── config/
│   ├── config.yaml         # Configuração da missão (origem, robôs, reamostragem, anomalias, saída, mapa, IA)
│   └── esquema.py          # Esquema Pydantic e leitura do YAML
├── geo/
│   └── transformacoes.py   # LLA ↔ ECEF ↔ NED, AER, heading e referencial do corpo em NumPy
├── io_dados/               # (chama-se io_dados e não io para não tapar o módulo io do Python)
│   ├── leitor.py           # Leitura e limpeza dos CSV, conversão para NED, t0 comum
│   └── exportacao.py       # CSV de telemetria configurável e relatório TXT
├── analysis/
│   ├── reamostragem.py     # Grelha temporal comum, interpolação linear e SLERP
│   ├── risco.py            # DCPA / TCPA
│   ├── anomalias.py        # Saltos de GPS, falhas de dados e acelerações anómalas
│   ├── validacao.py        # Velocidade do twist vs velocidade a partir das posições
│   └── resumo.py           # Distância mínima entre robôs
├── ai/
│   ├── ia_local.py         # Explicação por IA (Ollama ou API) com cache e texto por regras
│   └── voz.py              # Leitura em voz alta com o espeak-ng
├── ui/
│   ├── estilo.py           # Cores e estilos comuns
│   ├── mapa.py             # Mapa global e modo offline
│   ├── graficos.py         # Gráficos ao longo do tempo, distâncias e validação
│   ├── layout.py           # Layout da página
│   └── callbacks.py        # Callbacks do Dash (replay, radar, DCPA, IA, exportações)
├── tests/                  # Testes pytest (test_geodesia, test_dados, test_analysis, test_config, test_ia_local)
├── requirements.txt
├── pytest.ini
└── *.csv                   # Logs dos robôs na Aguçadoura (robot1_s1, robot4_s1, robot7_s1)
```
