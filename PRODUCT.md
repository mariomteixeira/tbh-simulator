# Product

## Register

product

## Users

O dev (Mario) — jogador de *TBH: Task Bar Hero* — e a namorada dele (o build
portátil roda no PC dela sem Python). Contexto de uso: olhadas rápidas no painel
**enquanto o jogo auto-batalha**, pra decidir o que farmar, qual gear trocar/subir,
qual runa/cubo comprar, onde estacionar offline e se dá pra passar a próxima fase.
Desktop, pt-BR. Não é app público.

## Product Purpose

**TBH Copilot** observa o save ao vivo, simula combate + economia e diz a **melhor
decisão**: melhor fase pra gold/exp, trocas de gear, compras de runa, alquimia de
cubo, parada offline, "dá pra passar essa fase?". **Read-only** — espelha o jogo,
nunca modifica. Sucesso = o jogador bate o olho e sabe o que fazer, sem ler textão.

## Brand Personality

Preciso, honesto com os dados, sem enrolação, de especialista. **Estética pixel-art**
— o copilot tem que parecer **parte do jogo** (TBH é pixel-art), não uma dashboard de
SaaS. Número e ícone acima de prosa. Caráter > neutralidade corporativa.

## Anti-references

- **Dashboard de SaaS genérica**: hero-metric template, grades de cards idênticos,
  tracking-eyebrows, gradientes roxos.
- **Tabelas como layout padrão** (a Farm hoje é uma tabela "de planilha" — sai disso).
- **"AI slop"**: parágrafos explicando a fórmula/cálculo. Entregar a INFO, não o ensaio.
- **Paleta espalhada**: ~10 cores de chrome competindo. Alvo: **≤3 cores de chrome**
  (cores de elemento/grau são DADO semântico do jogo, decidir como tratar à parte).
- Mostrar número estimado/inferido como se fosse real.

## Design Principles

1. **Dado real, nunca inferido** — toda informação rastreável ao datamine; senão, dizer que não tem.
2. **Decisão, não dado cru** — diga o que fazer, não só mostre tabela.
3. **Sem AI slop** — entregar a info de forma visual; cortar o textão explicativo.
4. **Pixel-art nativo** — parecer continuação do jogo, não um produto à parte.
5. **Densidade honesta + observador** — painel de especialista, read-only, espelha o jogo.

## Accessibility & Inclusion

Ferramenta pessoal, tema escuro, desktop-first, pt-BR. Não é WCAG-crítico, mas
**contraste importa** (regressão recente: grau Imortal saía branco no escuro).
Cor nunca pode ser o ÚNICO portador de significado (elemento/grau precisam de
rótulo/ícone além da cor) — ainda mais com a paleta enxuta.
