# TBH Copilot

Simulador/copilot **somente leitura** para *TBH: Task Bar Hero*. O backend em
Python vigia o `SaveFile_Live.es3`, decripta uma **cópia** do arquivo (nunca o
original), simula combate e economia, **aprende os tempos reais de clear com
os seus saves** e serve um painel React local que diz: a melhor fase para gold
e exp, quanto custa ficar na fase errada, onde estacionar antes de fechar o
jogo, que gear trocar e quando cada herói sobe de nível.

> **Por que é seguro.** O script só *lê* o save. Nada toca o processo ou a
> memória do jogo, o arquivo original jamais é aberto em modo escrita, e o
> jogo é single-player sem anticheat.

---

## Arquivos

| Arquivo | O que é |
|---|---|
| `server.py` | Backend FastAPI: vigia o save, roda o simulador, grava amostras, expõe `/api/snapshot` e serve o frontend buildado. |
| `simulator.py` | Engine próprio: DPS/EHP (validado exato contra o painel de Status do jogo), economia por estágio, regressão de tempos de clear, offline, comparador de gear, projeção de nível e coach em texto. |
| `store.py` | Persistência em `data/store.json`: amostras de clear + histórico de gold/exp (sobrevive a restarts). |
| `tbh_tracker.py` | Decriptação/parsing do save + taxas medidas entre saves (também é CLI standalone). |
| `fetch_gamedata.py` | Baixa as tabelas do jogo de `taskbarhero.wiki/data/` para `gamedata/`. |
| `frontend/` | Painel em React + Vite; o build vai para `frontend/dist`. |
| `validate.py` | Suite de validações (fórmulas, regressão, amostras, API). |
| `tbh_painel.pyw` / `criar_atalho.ps1` | Mini-janela de controle (Iniciar/Parar + status ao vivo) e o gerador do atalho na Área de Trabalho. |
| `reference/` | Clone do tbh-copilot **apenas para comparação** — nada do app depende dele. |

## Instalação e uso

```bash
pip install -r requirements.txt
python fetch_gamedata.py            # uma vez (e após updates do jogo: --force)

cd frontend && npm install && npm run build && cd ..   # uma vez

python server.py                    # abre http://127.0.0.1:8423
```

**Atalho fácil (Windows):** rode uma vez
`powershell -ExecutionPolicy Bypass -File criar_atalho.ps1` pra criar o atalho
**TBH Copilot** na Área de Trabalho. Ele abre o `tbh_painel.pyw` — uma
mini-janela com **Iniciar/Parar** e status ao vivo, que sobe o servidor e abre
o painel sem precisar de terminal.

Opções: `--save <caminho>`, `--port`, `--interval`, `--debounce`.
Validações: `python validate.py`.
Dev do frontend com hot-reload: `cd frontend && npm run dev` (proxy para a API).

---

## Como o modelo funciona

### Fórmulas (de `taskbarhero.wiki/mechanics`, validadas no jogo real)

- **Stacking:** `final = (base + ΣFlat) × (1 + ΣAdditive/1000) × Π(1 + Mult/1000)`
  somando herói + gear + encantos + passivas + runas (+ pet nos bônus de farm).
- **DPS de Status:** `AD × AS × (1 + CC×(CD−1)) × 1,9` — reproduz o painel do
  jogo com erro zero (validado nos 3 heróis do save de referência).
- **DPS efetivo:** Status × bônus de delivery/elemento + skills de cooldown.
- **Armadura:** `Red = Armor²/(Armor² + (14·Lvl+12)×(Armor+0,4·Dano))`, cap 75%.
- **Economia por estágio:** HP/gold/exp por clear a partir da composição real
  de monstros × escala do nível × multiplicadores de boss + runas flat por kill.

### Calibração que aprende sozinha

Cada par de saves no mesmo estágio vira uma **amostra de clear**: gold ganho ÷
gold por clear = nº de clears → tempo médio. As amostras ficam em
`data/store.json` com o DPS do momento. Com 3+, o modelo ajusta por regressão
ponderada (meia-vida de 14 dias):

```
clearSec = T_fixo + tWave·waves + HP / (c · DPS_do_time)
```

`tWave` (overhead por wave) e `c` (eficiência de kill) saem dos **seus dados**.
Sem amostras, o modelo ancora no gold/h medido da sessão; sem nada, usa o
modelo puro. A fonte da calibração aparece no painel.

Na aba **Modelo** você também pode **cronometrar uma run e digitar o tempo em
segundos** ("Calibrar tempo de clear"): vale como verdade-base de **peso alto**
e **um único tempo já ancora** a eficiência de kill — não depende da contagem
de kills nem do HP da wiki. Com 5+ amostras a regressão passa a ajustar também
o overhead fixo (`T_fixo`), e o relógio usa o `playTime` (ignora tempo de jogo
fechado).

### O que o painel entrega

- **Coach em texto** — melhor fase de gold, custo por hora da fase errada,
  prontidão do push, estacionamento offline, trocas de gear que valem.
- **Tabela de farm** — gold/h e exp/h reais por estágio, ordenável e filtrável,
  com tempo de clear e perigo relativo ao seu estágio atual.
- **Projeção de nível** — curva de 24h por herói no ritmo medido.
- **Gear** — varre o inventário e mostra trocas com ganho de power, por slot.
- **Offline** — melhor fase para deixar o jogo parado (cap de 8h).

## Limitações conhecidas

- O perigo é relativo ao estágio atual; buffs ativos e falloff de exp por
  over-level não são modelados.
- A 1ª sessão começa sem amostras: deixe o painel aberto enquanto joga que a
  precisão sobe sozinha.

## Créditos

- Dados e mecânicas: **taskbarhero.wiki** (fan-made). Conteúdo do jogo pertence
  aos respectivos donos. Projeto fan-made, não afiliado ao desenvolvedor.
