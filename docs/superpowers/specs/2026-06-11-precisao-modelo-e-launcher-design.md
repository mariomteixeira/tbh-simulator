# Design — Precisão do modelo + launcher

Data: 2026-06-11
Status: aprovado em conversa (aguardando revisão do spec escrito)

## Objetivo

Duas entregas, construídas juntas:

1. **Launcher** — uma mini-janela pra ligar/desligar o servidor e ver que está
   funcionando, sem terminal.
2. **Precisão do modelo** — hoje o tempo de clear e o exp/h são imprecisos.
   Atacar isso com (a) tempo de run informado pelo usuário como verdade-base,
   (b) limpeza/ajuste do modelo de tempo, (c) curva real de EXP por nível.

Toda interação de dados fica **no painel web**. O launcher só controla o
processo e mostra status.

---

## Fato do jogo que orienta o design

Confirmado jogando: o **auto-battle nunca pausa** — menu, craft e portal seguem
matando. `currentStage` só muda ao **trocar de mapa**. Consequências:

- `totalKills` **não** serve como sinal de "idle" (kills nunca param). Não dá
  pra gatear janela por kills nem confiar na contagem de kills/run.
- O único contaminante real da janela automática é a **troca de fase no meio
  do intervalo** (e jogo fechado, que `playTime` já descarta).
- Logo: **tempo cronometrado pelo usuário + DPS do momento** é a observação
  mais limpa que existe — não depende de kills nem do HP da wiki.

---

## Componente 1 — Launcher (`tbh_painel.pyw`)

Mini-janela Tkinter (~360×300), sem dependência nova, sem terminal (`.pyw`).

- **Status**: bolinha `● Rodando` / `● Parado`.
- **Iniciar**: sobe `server.py` como subprocesso usando `sys.executable`
  (mesmo interpretador 3.12 que tem fastapi/uvicorn) e abre o navegador em
  `http://127.0.0.1:8423`. Botão desabilita enquanto roda.
- **Parar**: encerra o subprocesso. Bolinha volta pra Parado.
- **Abrir painel**: reabre o navegador.
- **Info ao vivo** (poll de `/api/snapshot` a cada ~2s enquanto roda): save
  encontrado, gamedata ok, idade da última leitura, estágio atual, gold/h e
  exp/h da sessão, nº de amostras de clear, erros (em vermelho).
- **Fechar a janela (X)** → para o servidor junto (sem processo órfão).
- **Atalho** "TBH Copilot" na Área de Trabalho → `pythonw.exe tbh_painel.pyw`
  (gerado via `WScript.Shell` em PowerShell, apontando pro `pythonw` 3.12).

Sem botões de Pausar e sem entrada de dados (decisão do usuário).

---

## Componente 2 — Calibração manual de tempo (painel web + API)

### Servidor (`server.py`)
- `POST /api/calibration` com `{stage, clearSec}` → grava amostra manual
  anexando o contexto atual: `{ts, stage, clearSec, partyDps (atual), hp,
  waves, lvl, source:"manual"}`.
- `DELETE /api/calibration/{stage}` → remove a calibração manual da fase.
- A lista de calibrações manuais entra no `/api/snapshot` (pra UI listar).
- O save **nunca** é tocado — só escreve em `data/store.json`.

### Store (`store.py`)
- Amostras passam a carregar `source` (`"manual"` | `"auto"`).
- Manual: no máximo uma por fase (sobrescreve); auto: como hoje.
- `add_manual_sample` / `remove_manual_sample` / expor manuais no snapshot.

### Frontend (painel React)
- Bloco "Calibrar fase atual" ao lado da tabela de farm: mostra a fase atual,
  campo `tempo de clear: __ s`, botão salvar. Lista as calibrações manuais já
  feitas com botão de remover. (Espelha o override manual do tbh-copilot.)

---

## Componente 3 — Modelo de tempo de clear (`simulator.py`)

Mantém o esqueleto físico `clearSec = T_FIXO + tWave·waves + HP/(c·DPS)`.
Mudanças:

1. **Peso manual >> auto.** No `fit_clear_model`, amostra `source:"manual"`
   recebe peso alto fixo (default `W_MANUAL = 20`, equivalente a uma janela
   auto perfeita ~4× saturada); auto segue `0.5^(idade/14d) · min(clears,5)`.
   Constante tunável.
2. **Ajustar `T_FIXED` também.** Hoje é constante chutada. Passar a regressão
   pra 3 parâmetros: `clearSec = a + tWave·waves + q·(HP/DPS)` (a=T_FIXO,
   q=1/c). Se mal-condicionado ou com poucos pontos (< 5), cai pro ajuste
   atual de 2 parâmetros com `T_FIXED` fixo.
3. **Relógio = `playTime`.** A janela em `make_clear_sample` passa a medir
   `dt` por `playTime` (segundos, já em `parse_state`) em vez de
   `lastSavedTime` — descarta tempo de jogo fechado. Reset por troca de fase
   continua descartando intervalos que cruzam mapa.
4. **Termo de EHP (fases-parede) — atrás de flag, calibrar depois.** Fator de
   lentidão opcional ligado ao `danger` já calculado; **desligado por padrão**
   até haver tempos manuais em fases-parede pra calibrar. Documentado como v2.

---

## Componente 4 — Curva de EXP por nível (`simulator.py` `fit_factor`)

Trocar a logística de um lado só pela curva **empírica** medida no jogo
(herói Lv41), função de `δ = stage_lvl − hero_lvl`:

| δ | EXP mantida |
|---|---|
| −16 | 0.05 |
| −12 | 0.16 |
| −8 | 0.50 |
| −5 | 0.88 |
| −3 | 0.99 |
| −2 … +6 | 1.00 (platô) |
| +10 | 0.85 |

- Interpolação **linear** entre os nós; clamp `[0.01, 1.0]`.
- Tails (extrapolados, incertos): abaixo de −16 segue a inclinação do último
  trecho com piso ~0.02; acima de +10 segue declínio leve com piso ~0.30.
- Assume invariância em `δ` entre níveis (só temos dados do Lv41); refinar se
  o usuário trouxer outra faixa.
- A ancoragem por exp/h medido (`exp_scale`) continua igual.

---

## Validação (`validate.py`)

- `fit_factor` reproduz a tabela dentro de ±2 p.p. nos nós.
- Ajuste de 3 parâmetros recupera `T_FIXO/tWave/c` conhecidos em dados
  sintéticos; degrada pro de 2 parâmetros quando mal-condicionado.
- Amostra manual domina o ajuste sobre várias auto conflitantes.
- `POST/DELETE /api/calibration` faz round-trip no `store.json`.

## Notas

- O repositório **não é um repo git** — o spec não será commitado (posso rodar
  `git init` se você quiser versionar; senão segue sem).
- Ordem sugerida de implementação: Componente 4 (curva exp, isolado e rápido) →
  Componente 1 (launcher) → Componentes 2+3 (calibração manual + modelo, que
  andam juntos).
