# Frontend — TBH Copilot

Painel React servido pelo `server.py` (estático, de `frontend/dist`). Lê o save
ao vivo via polling de `/api/snapshot`.

## Stack
- **React 18 + Vite 5 + Tailwind v4** (`@tailwindcss/vite`).
- **@xyflow/react** — só na árvore de runas (`RunesPage`).
- Sem TypeScript. Sem router (hash routes manuais).

## Build / deploy (IMPORTANTE)
- Dev: `cd frontend && npm run build` → gera **`frontend/dist`**.
- O `server.py` serve `frontend/dist` como estático (não o source). **Toda
  mudança no frontend exige `npm run build`** e o `frontend/dist` é
  **versionado de propósito** (o updater/portátil baixa o dist pronto do
  GitHub — o PC da namorada não tem Node). Sempre commitar o `dist` junto.
- Reiniciar o `server.py` NÃO é preciso pra ver mudança de frontend (dist é
  estático), mas É preciso pra mudança de **backend** (simulator.py recarrega só
  ao subir o processo).

## Estrutura
- `src/App.jsx` — shell (sidenav + topbar), `ROUTES`, `useRoute` (hash), e as
  funções de página que devolvem `{main, rail}`. RunesPage e CubePanel são
  full-width (caso especial no render).
- `src/useSnapshot.js` — polling de `/api/snapshot` (~2s) → `{version, status,
  state, rates, sessionRates, sim, history, manualSamples}`. `version` = versão do
  copilot (`.version` deployado, ou package.json + sha) pra topbar.
- `src/format.js` — `fmt` (números), `fmtDur`, `fmtHours`, `timeAgo`.
- `src/statNames.js` — `elemPt` (elemento→pt), nomes de stat.
- `src/styles.css` — **sistema PIXEL-ART** (uma folha só): tokens warm + fontes
  **Pixelify Sans** (títulos/palavras) / **Silkscreen** (rótulos) / **JetBrains
  Mono** (corpo + TODO número). Spec visual = ver "Design system" abaixo.
- `src/grades.js` — fonte ÚNICA de cor/label de grau (`gradeOf`/`gearPt`).
- `src/components/`:
  - `CombatPanel` — combate por fase (`sim.combat`). **Topo de Heróis & Gear.**
  - `DamagePanel` — dano por skill (`sim.heroes[].damage`: auto/skills/buffs/utility).
  - `GearPanel` — DUAS seções (gear é DESACOPLADO da fase): "build pra uma
    fase" (`sim.gear.byStage`, com `<select>` de fase) + "upgrades diretos"
    (`sim.gear.general`, cenário neutro). Exporta `RoleTag` (tank/dps/healer).
  - `Heroes` — rail de Heróis & Gear (stats por herói).
  - `CubePanel` — aba Cubo (`sim.alchemy`): grade 7×7 estilo stash + detalhe/preview.
  - `RunesPage` — árvore de runas (xyflow).
  - `FarmTable` / `BoxPanel` / `OfflinePanel` / `ModelTab` — Farm / Baús / Offline / Modelo.

## Rotas (ROUTES em App.jsx)
`farm` (`#/`, **default**) · `boxes` (#/baus) · `cube` (#/cubo) · `runes`
(#/runas) · `heroes` (#/herois = "Heróis & Gear") · `offline` · `model`.
(A antiga "Visão geral" foi REMOVIDA — Farm é a principal.)

## Forma do `sim` (de simulate() no simulator.py)
`party{dps,ehpMin}`, `heroes[]{key,name,cls,role,level,dps,statusDps,buffDps,
dpsBuffed,ehp,damage{auto,skills,buffs,utility},stats}`, `farm{rows,current,
bestGold,bestExp,push,bestBossBox,bestNormalBox,dropBonus,ceiling}`,
`combat[]{label,tag,name,lvl,diff,current,elements,partyDps,clearTime,ehpMin,
hitsToDie,threat,weakestHero,verdict,bottleneck,rating,needResist{element,points,
hits,capped,resNow,resTarget}}`, `gear{general[]{cls,role,wDps,basePower,
slots[]{gearType,current,upgrade{name,grade,level,dPower,dDps,dEhp,statDiff}}},
byStage[]{key,label,name,tag,lvl,diff,current,heroes[](igual a general)}}`,
`alchemy{cube{level,exp,need,nextNeed,
recoLevel,recoMatch},buff,containers[],projectAll,sumAll}`, `offline`, `runes`,
`projection`, `levelEta`, `coach`.

## Design system PIXEL-ART (V1 — FEITO)
Reskin completo pra estética pixel-art (o jogo TBH é pixel-art). Referência viva:
foi prototipado em `frontend/pixel-mockup.html` (já apagado — o app É a referência).
- **3 cores de chrome** (e só tons/alpha delas): `--bg #0f0e0c` (near-black quente),
  `--ink #ece2cf` (bone), `--accent #f3b340` (gold). NÃO espalhar acentos novos.
- **Camada semântica à parte** (não conta no "3"): grau, elemento e estado — sempre
  cor **+ rótulo/letra** (nunca só cor). Grau via `grades.js` (`gradeOf`): common
  #9c937f, uncommon #54fc0c, rare #2f8bfc, legendary #fc9c0c, immortal #fc2424,
  arcana #b40cfc, **beyond #fc246c**, **celestial #6ccce4**, divine #fce454,
  **cosmic = holo** (`special:true`, sem cor flat no wiki — gradiente). Cores do wiki.
- **Primitivas**: cantos retos (`*{border-radius:0}`), bordas hard 2px, **sombra
  chapada com offset** (sem blur), `image-rendering:pixelated`, scanline sutil no body.
  PROIBIDO: gradiente (exceto holo do cosmic), glassmorphism, side-stripe border.
- **Tipografia**: números SEMPRE em mono (Pixelify nos dígitos vira "8-8").
- **Farm = cards** (`.stage`), NÃO tabela. Ordenação por chips no header.
- **Nav** com ícones pixel (SVG `crispEdges`, `currentColor`) por rota (defs em
  `App.jsx > NavIcons`). **Topbar** mostra a versão do copilot (`d.version` do snapshot).
- **Sem "AI slop"**: entregar a INFO visual, sem textão explicando fórmula.

## Imagens / rotas de asset (proxy do wiki, UA de navegador)
- Ícone de item: `/itemicon/{key}.png` (de `items[key].icon`).
- **Portrait de herói**: `/heroicon/{key}.png` (de `heroes[key].icon`) — usado em
  `Heroes`/`DamagePanel` via `.spr`. SÓ portrait estático; **não há gif** na datamine
  (a wiki anima via `SpriteAnimator`/spritesheet — não rastreado). Ver [[tbh-pixelart-redesign]].

## Pendente
- Cores de **elemento** (fogo/gelo/raio/chaos) ainda PROVISÓRIAS (wiki não expõe
  `--color-fire`); confirmar antes de fixar.
- **Cosmic**: cor real não confirmada (holo placeholder).
- Opcional: animar heróis (achar o spritesheet do `SpriteAnimator` + `steps()`).
