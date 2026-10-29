<span style="color:#9A1A24;text-align:center">

# TÓPICOS DE MATEMÁTICA PARA SISTEMAS AUTÓNOMOS

<div style="text-align: right"><i>  </i></div>

***
<center><h1> TRABALHO LETIVO - ENTREGA 1 </h1></center>

***
<span style="color:#000000;text-align:LEFT">

**Nota 1**: Todos elementos do grupo são responsáveis por esta entrega<br>
**Nota 2**: Todos elementos do grupo tomaram conhecimento das regras estabelecidas para o funcionamento da u.c. no [**Moodle do ISEP**](https://moodle.isep.ipp.pt)<br>

***

## GRUPO
> N: 1231182  Nome: Juliana Rodrigues  \
> N: [NÚMERO DO COLEGA]  Nome: [NOME DO COLEGA]  \

# Conteúdo

- [1. Identificação dos objetivos e estruturação do problema](#1.-Identificação-dos-objetivos-e-estruturação-do-problema)     
- [2. Justificação da relevância das bibliotecas Python selecionadas](#2.-Justificação-da-relevância-das-bibliotecas-Python-selecionadas)     
- [3. Metodologia proposta para o desenvolvimento do projeto](#3.-Metodologia-proposta-para-o-desenvolvimento-do-projeto)


## 1. Identificação dos objetivos e estruturação do problema
[De volta para  "Conteúdo"](#Conteúdo)
### 1.1 Contexto e objetivo geral

Os veículos robóticos marinhos geram, durante cada missão, registos (*logs*) com a sua pose, velocidades e incerteza associada. Analisar estes registos apenas como tabelas de números dificulta perceber **onde estava cada robô, para onde apontava e como se relacionava com os restantes** ao longo do tempo.

O objetivo do projeto é desenvolver um **dashboard web em Python e Dash** que permita **reproduzir (*replay*) missões** de robôs marinhos a partir de **dados reais do INESC TEC recolhidos na Aguçadoura**, visualizando as trajetórias em dois tipos de referencial:

- **referencial global**: todos os robôs sobre um mapa geográfico;
- **referencial local**: o ponto de vista de um robô selecionado, com os restantes robôs expressos relativamente a ele.

A missão em estudo envolve **3 robôs**, pelo que a vista local pode ser pedida para qualquer um deles e o referencial **roda com o *heading* do robô selecionado**.

### 1.2 Dados de entrada

Os dados são ficheiros **CSV no formato ROS**, com os seguintes grupos de campos:

| Grupo | Campos | Observações |
|---|---|---|
| Tempo e identificação | `header.stamp`, `child_frame_id` | instante da medição e identificador do veículo |
| Pose (posição) | Latitude, Longitude, Altitude | coordenadas geodésicas (LLA) |
| Pose (orientação) | Quaternion (`x`, `y`, `z`, `w`) | convenção ROS: ordem `x, y, z, w` |
| Velocidades | lineares e angulares | a confirmar o referencial em que estão expressas |
| Incerteza | matriz de covariância com 36 elementos | corresponde a uma matriz 6×6 |
| *Surface Reference* | Lat 41.452…, Lon −8.813…, Alt 55.447… | origem global fornecida (valores completos a usar a partir dos dados) |

A *Surface Reference* é usada como **origem (0, 0, 0)** do sistema de coordenadas local NED.

### 1.3 Requisitos a cumprir

| N.º | Requisito | Entregável concreto |
|---|---|---|
| 1 | **Global View** | Mapa global (ex.: OpenSeaMap) com todos os robôs, trajetórias e identificação por cores |
| 2 | **Local View** | Seleção de um robô, representação do seu *heading* e transformação da posição dos vizinhos para o referencial relativo |
| 3 | **Mission Replay** | Slider de tempo com botões *Play/Pause* para animar a missão e saltar para instantes específicos |
| 4 | **Configuração YAML** | Leitura dos *logs* e das cores dos robôs a partir de um ficheiro `.yaml` |
| 5 | **Output** | Geração e configuração de *logs* de saída a partir do dashboard |

### 1.4 Estruturação do problema

O problema decompõe-se em quatro blocos encadeados:

```text
 ENTRADAS                  PROCESSAMENTO                         SAÍDAS
 --------                  -------------                         ------
 config.yaml  ─┐
               ├─►  leitura + validação ─► LLA → ECEF → NED ─►  Global View
 logs CSV     ─┘        (pydantic, pandas)   quaternion → yaw     Local View
                                              reamostragem        Replay (slider)
                                              (grelha temporal    Exportação de logs
                                               comum, SLERP)      Mission Control (IA)
```

**Decisões de estruturação:**

1. O **pré-processamento corre uma só vez no arranque** (leitura, conversão de coordenadas, reamostragem). Durante o *replay* nada disto é recalculado.
2. O **slider de tempo é o relógio único**: mapa, vista local e gráficos reagem ao seu valor.
3. A **componente de IA é independente** do caminho de animação, para nunca bloquear a interface.

### 1.5 Formulação matemática

**a) LLA → ECEF (elipsoide WGS84).** Com $a = 6378137\,\text{m}$, $f = 1/298.257223563$ e $e^2 = f(2-f)$, o raio de curvatura na vertical principal é

$$N(\varphi) = \frac{a}{\sqrt{1 - e^2 \sin^2\varphi}}$$

e as coordenadas ECEF de um ponto $(\varphi, \lambda, h)$ são

$$x = (N + h)\cos\varphi\cos\lambda, \qquad y = (N + h)\cos\varphi\sin\lambda, \qquad z = \big(N(1-e^2) + h\big)\sin\varphi$$

**b) ECEF → NED.** Com a *Surface Reference* $(\varphi_0, \lambda_0, h_0)$ como origem e $\mathbf{p}_0$ a sua posição ECEF,

$$\begin{bmatrix} n \\ e \\ d \end{bmatrix} = \mathbf{R}_{ned}\,(\mathbf{p} - \mathbf{p}_0), \qquad
\mathbf{R}_{ned} = \begin{bmatrix}
-\sin\varphi_0\cos\lambda_0 & -\sin\varphi_0\sin\lambda_0 & \cos\varphi_0 \\
-\sin\lambda_0 & \cos\lambda_0 & 0 \\
-\cos\varphi_0\cos\lambda_0 & -\cos\varphi_0\sin\lambda_0 & -\sin\varphi_0
\end{bmatrix}$$

Por construção, a origem converte para $(n, e, d) = (0, 0, 0)$.

**c) Orientação.** O *quaternion* é convertido para ângulos de Euler (*yaw*, *pitch*, *roll*). O ROS usa tipicamente ENU (*yaw* nulo a Este, sentido anti-horário), enquanto a bússola e o NED usam 0° a Norte, sentido horário. A conversão típica é

$$\psi_{\text{bússola}} = 90^\circ - \text{yaw}_{ENU}$$

A convenção efetiva será **validada comparando o *yaw* com a direção real do movimento** (*course over ground*).

**d) Vista local (referencial do corpo).** Para um robô de referência com *heading* $\psi$ e um vizinho com diferença NED $(\Delta n, \Delta e)$:

$$x_b = \Delta n\cos\psi + \Delta e\sin\psi \quad (\text{frente}), \qquad y_b = -\Delta n\sin\psi + \Delta e\cos\psi \quad (\text{direita})$$

$$\text{alcance} = \sqrt{\Delta n^2 + \Delta e^2}, \qquad az_{rel} = \big(\operatorname{atan2}(\Delta e, \Delta n) - \psi\big) \bmod 360^\circ$$

Esta é a representação AER (*Azimuth-Elevation-Range*) relativa ao robô. Para robôs à superfície a elevação é aproximadamente nula, mas a formulação mantém-se válida para veículos com profundidade:

$$el = \operatorname{atan2}\!\big(-\Delta d,\ \sqrt{\Delta n^2 + \Delta e^2}\big)$$

### 1.6 Extensão proposta: análise assistida por IA ("Mission Control")

Para além dos cinco requisitos, propomos uma aba *Mission Control* com **IA generativa**. Como um modelo de linguagem não lida bem com milhares de coordenadas, o Python calcula **primeiro** estatísticas e eventos, e só envia à IA um **resumo estruturado** (JSON):

- distância mínima entre robôs e, para cada par, o ponto de maior aproximação (DCPA/TCPA);
- saltos de GPS e velocidades fisicamente impossíveis;
- falhas de dados (*dropouts*) e anomalias nas acelerações.

Para dois robôs com posição relativa $\mathbf{r}$ e velocidade relativa $\mathbf{v}$:

$$t_{CPA} = -\frac{\mathbf{r}\cdot\mathbf{v}}{\lVert\mathbf{v}\rVert^2}, \qquad d_{CPA} = \lVert\mathbf{r} + \mathbf{v}\,t_{CPA}\rVert$$

A IA gera um **relatório de missão** e/ou **explica o que acontece num instante** quando o utilizador faz pausa no *replay*. Esta componente é tratada como **extensão**: o núcleo obrigatório (requisitos 1 a 5) tem prioridade.

### 1.7 Pressupostos e questões em aberto

**Pressupostos de trabalho** (a confirmar com os dados e com o docente):

- O requisito 5 ("gerar e configurar *logs* de saída") é interpretado como a exportação, a partir do dashboard, de um CSV processado (NED, *heading*, janela temporal escolhida), de um *log* de eventos e do relatório, com a configuração de saída também em YAML (campos, referencial, taxa, intervalo).
- A altitude da *Surface Reference* e a dos dados são do mesmo tipo (elipsoidal ou ao nível médio do mar). Se não forem, será aplicada a correção adequada.
- A ordem dos eixos da matriz de covariância 6×6 e o referencial em que está expressa serão verificados antes de qualquer utilização (por exemplo, elipses de incerteza).

**Questões a esclarecer:**

1. Confirmação da interpretação do requisito 5.
2. Referencial em que estão expressos os *quaternions* e as velocidades (ENU ou NED; mundo ou corpo).

## 2. Justificação da relevância das bibliotecas Python selecionadas
[De volta para "Conteúdo"](#Conteúdo)

A seleção de bibliotecas segue três critérios: **(i)** operações **vetorizadas** sobre colunas inteiras (sem ciclos linha a linha); **(ii)** possibilidade de **validação cruzada** das transformações matemáticas; **(iii)** manutenção ativa e boa integração entre si.

### 2.1 Matemática e dados

| Biblioteca | Função no projeto | Justificação |
|---|---|---|
| **NumPy** | Implementação própria das fórmulas WGS84 (LLA → ECEF → NED), rotação para o referencial do corpo, DCPA/TCPA | Operações vetorizadas sobre arrays completos; permite demonstrar que se compreende a matemática e não apenas chamar uma função. |
| **pandas** | Leitura dos CSV, indexação temporal, reamostragem, filtragem por robô | Estrutura natural para séries temporais; aceita colunas diretamente nas funções NumPy/pymap3d. |
| **SciPy** (`scipy.spatial.transform`) | `Rotation` para *quaternion* → Euler; `Slerp` para interpolar orientações | Evita interpolar ângulos linearmente (problema de *wrap-around* a ±180°); usa a mesma ordem `x, y, z, w` do ROS. |
| **pymap3d** | `geodetic2ecef`, `ecef2ned`, `geodetic2ned`, `geodetic2aer` | Biblioteca de referência para geodesia; vetorizada; usada como **validação independente** da implementação própria. |
| **pyproj** | Conversão EPSG:4979 → EPSG:4978 (LLA → ECEF) | Segunda validação independente, baseada na biblioteca PROJ. |

### 2.2 Interface e visualização

| Biblioteca | Função no projeto | Justificação |
|---|---|---|
| **Dash** | Servidor web, *layout* e *callbacks* | Modelo reativo (o slider como relógio único); `dcc.Interval` para o *replay*; `Patch()` para atualizar só os marcadores; *background callbacks* para a IA; `dcc.Download` para o *output*. |
| **Plotly** | Mapa geográfico, gráficos temporais, `Scatterpolar` para a vista local | Integração nativa com Dash. Adoção das funções recentes `line_map` e `scattermap` (MapLibre), suportando *layers* raster para acrescentar os *tiles* do OpenSeaMap, garantindo que a aplicação não depende de chaves comerciais (tokens) do Mapbox. |

### 2.3 Configuração, validação e qualidade

| Biblioteca | Função no projeto | Justificação |
|---|---|---|
| **PyYAML** | Leitura e escrita dos ficheiros de configuração (requisitos 4 e 5) | Formato legível por humanos; permite definir robôs, *logs*, cores e *output* sem alterar código. |
| **pydantic** | Validação do esquema do YAML | Erros claros e antecipados (campo em falta, tipo errado, cor inválida) em vez de falhas a meio da execução. |
| **pytest** | Testes automáticos das transformações | Garante que a origem converte para (0, 0, 0), *round-trip* LLA → NED → LLA e concordância com `pymap3d`. |

### 2.4 Componente de IA e execução em segundo plano

| Biblioteca | Função no projeto | Justificação |
|---|---|---|
| **SDK LLM / requests** | Chamada à API de IA generativa | Envio de um prompt curto com factos calculados; temperatura baixa; chave lida de variável de ambiente. |
| **diskcache** | *Background callbacks* do Dash e *cache* por *frame* | A chamada externa não bloqueia a animação; a mesma pergunta não é paga duas vezes. |

### 2.5 Estratégia de validação cruzada

A **implementação própria em NumPy** é a referência do trabalho e o **`pymap3d`** (e o `pyproj`) funcionam como oráculos nos testes. Se as duas implementações coincidirem dentro de uma tolerância numérica definida, ganha-se confiança nas fórmulas e fica documentado o erro obtido.

## 3. Metodologia proposta para o desenvolvimento do projeto
[De volta para "Conteúdo"](#Conteúdo)

### 3.1 Princípios orientadores

1. **Núcleo primeiro, extensões depois.** Os requisitos 1 a 5 são fechados antes de se avançar para a IA.
2. **Calcular uma vez, mostrar muitas.** Todo o processamento pesado é feito no arranque; o *replay* apenas lê dados já prontos.
3. **Validar antes de visualizar.** As transformações geodésicas têm testes automáticos antes de alimentarem qualquer gráfico.
4. **Robustez para a demonstração.** *Fallbacks* para tudo o que depende de rede (mapa e IA).

### 3.2 Arquitetura de software

Estrutura modular do repositório:

```text
projeto/
├── config/       # config.yaml e esquema pydantic
├── io/           # leitura dos CSV e escrita das saídas
├── geo/          # LLA → ECEF → NED, quaternion → yaw, referencial do corpo
├── analysis/     # reamostragem, DCPA/TCPA, deteção de anomalias
├── ai/           # prompt estruturado, chamada ao LLM, relatório por template
├── ui/           # layout e callbacks do Dash
└── tests/        # testes pytest
```

### 3.3 Arquitetura dos *callbacks* do Dash

```text
[Botão Play/Pause] ──► Interval.disabled
[Interval (tick)]  ──► Slider.value  (+ passo × velocidade)
[Slider.value]     ──► Mapa / Vista local / Gráficos      (Patch(), atualização parcial)
[Botão "Explicar"] ──► Relatório IA                        (callback separado, em segundo plano)
```

- Os dados ficam em memória no servidor, em estruturas só de leitura; `dcc.Store` guarda apenas estado pequeno (robô selecionado, velocidade).
- As trajetórias são desenhadas **uma só vez**; a cada instante atualizam-se apenas os marcadores da posição atual com `Patch()`.
- O slider usa `updatemode="mouseup"` para que arrastar não dispare dezenas de *callbacks*; o intervalo do `dcc.Interval` é escolhido acima do tempo de renderização medido.
- A chamada à IA tem *timeout*, *cache* por *frame* e *fallback* por *template* (mesmos factos, sem IA).

### 3.4 Fases de desenvolvimento

| Fase | Tarefas | Resultado verificável | Prazo |
|---|---|---|---|
| **1. Base** | Repositório e ambiente; exploração dos CSV; leitura de YAML e CSV; conversões geodésicas e testes | Origem → (0, 0, 0); implementação própria concorda com `pymap3d` | [Inserir Data] |
| **2. Global View e Replay** | Reamostragem para grelha comum (SLERP); mapa com OpenSeaMap; trajetórias coloridas; slider e *Play/Pause* | Replay fluido com os 3 robôs sobre o mapa | [Inserir Data] |
| **3. Local View** | Seleção de robô; referencial do corpo; vizinhos; *heading* | Vizinhos corretos quando o robô de referência roda | [Inserir Data] |
| **4. Output** | Exportação de CSV processado, *log* de eventos e relatório; configuração de saída em YAML | Ficheiros gerados a partir do dashboard | [Inserir Data] |
| **5. Extensões** | Eventos (DCPA/TCPA, saltos de GPS); *Mission Control* com IA | Relatório de missão com factos calculados | [Inserir Data] |
| **6. Fecho** | Testes finais; README; relatório; ensaio da demonstração | Execução do zero em máquina limpa | [Inserir Data] |

### 3.5 Validação

Testes automáticos (`pytest`):

- a *Surface Reference* converte para $(0, 0, 0)$;
- *round-trip* LLA → NED → LLA com erro desprezável;
- aproximadamente 111 km por grau de latitude;
- implementação própria vs. `pymap3d`/`pyproj`, com erro máximo registado;
- *heading* calculado vs. direção real do movimento (verificação da convenção de eixos).

Validação dos dados: deteção de saltos de GPS, falhas temporais e *timestamps* repetidos; o tempo é tratado **relativo ao início da missão** para evitar perda de precisão em *float*. Adicionalmente, será feita a limpeza prévia de dados: remoção de valores `NaN` nas poses e eliminação de *timestamps* duplicados antes da interpolação SLERP, para garantir a estabilidade do algoritmo.

### 3.6 Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Convenção de eixos/heading errada (ENU vs NED) | Validar o *yaw* contra a direção real do movimento |
| Robôs com *timestamps* diferentes | Reamostrar para grelha comum; SLERP para orientação; não interpolar através de falhas longas |
| Animação lenta ou a bloquear | `Patch()`, pré-processamento no arranque, medir o tempo dos *callbacks* |
| Mapa sem acesso à rede na demonstração | *Cache* de *tiles* ou modo offline |
| API de IA indisponível ou resposta errada | *Fallback* por *template*, *cache*, temperatura baixa e factos mostrados ao lado do texto gerado |
| Chave de API exposta | Variável de ambiente; nunca no repositório nem no YAML |
| Requisito 5 ambíguo | Confirmar interpretação com o docente |

### 3.7 Divisão de tarefas

| Elemento | Responsabilidades principais |
|---|---|
| Aluno 1 (Juliana) | Motor de Dados (Backend), implementação da matemática vetorial (NumPy), validação cruzada com `pymap3d` e estrutura do `config.yaml`. |
| Aluno 2 (Colega) | Interface Web (Frontend em Dash), otimização dos *callbacks* de animação e mapas (`Patch`), gestão de estados e integração da API de Inteligência Artificial. |

*Nota: Todas as decisões de arquitetura estrutural e a validação das transformações matemáticas são revistas em conjunto por ambos os elementos do grupo.*

### 3.8 Entregáveis

Código-fonte organizado em módulos, `config.yaml` de exemplo, testes automáticos, README com instruções de execução, relatório com diagrama de arquitetura, derivação matemática e resultados de validação, e demonstração do dashboard.

</span>
