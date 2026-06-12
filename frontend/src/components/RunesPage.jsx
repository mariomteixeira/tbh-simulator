import React, { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Controls,
  MiniMap,
  Handle,
  Position,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { fmt } from "../format.js";
import { runeStatPt } from "../statNames.js";

const TILE = 48; // tile quadrado, grade da wiki tem passo 72 (gap 24)

function nodeState(n) {
  if (n.maxed) return "maxed";
  if (n.owned) return "owned";
  if (n.unlocked) return n.gain?.affordable ? "buyable afford" : "buyable";
  return "locked";
}

function RuneNode({ data }) {
  const n = data.n;
  const rk = data.rank; // {kind: "c"|"f", rank: 1..3} ou undefined
  const cls =
    "rune-tile " + nodeState(n) +
    (data.selected ? " sel" : "") +
    (rk ? ` rk rk-${rk.kind}${rk.rank}` : "") +
    (data.inPath ? " inpath" : "");
  const tip =
    `${n.name} — nv ${n.level}/${n.max}` +
    (n.unlocked
      ? n.maxed ? " (máxima)" : ` · próx: ${fmt(n.nextCost)} gold`
      : ` (bloqueada, pai nv ${n.req})`);
  return (
    <div className={cls} title={tip}>
      <Handle type="target" position={Position.Top} className="rh" />
      <img src={`/runeicons/${n.icon}.png`} alt="" draggable={false} />
      <span className="rt-lv">{n.level}/{n.max}</span>
      {rk && <span className={`rt-rank rr-${rk.kind}`}>{rk.rank}º</span>}
      {data.needLevel != null && <span className="rt-need">nv{data.needLevel}</span>}
      <Handle type="source" position={Position.Bottom} className="rh" />
    </div>
  );
}

const nodeTypes = { rune: RuneNode };

function RecList({ title, recs, onPick, showSteps, kind }) {
  if (!recs?.length) return null;
  return (
    <div>
      <h3>{title}</h3>
      <div className="rec-list">
        {recs.map((r, i) => (
          <button className="rec" key={r.key + "-" + r.level} onClick={() => onPick(r.key)}>
            {kind ? (
              <span className={`rec-rank rr-${kind} p${Math.min(i + 1, 4)}`}>{i + 1}º</span>
            ) : (
              <span className="rec-rank dim">{i + 1}º</span>
            )}
            <img src={`/runeicons/${r.icon}.png`} alt="" />
            <span className="rec-body">
              <span className="rec-name">
                {r.name} <em>nv {r.level}</em>
              </span>
              <span className="rec-gain">{r.label}</span>
              {showSteps && r.firstStep && (
                <span className="rec-step">
                  {r.steps} passo(s) · 1º: {r.firstStep.name} → nv{r.firstStep.toLevel}
                </span>
              )}
            </span>
            <span className={"rec-cost" + (r.affordable ? " ok" : "")}>
              {fmt(r.cost)} <em>gold</em>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function RuneDetails({ n, onPick }) {
  return (
    <div>
      <h3>Runa selecionada</h3>
      <div className="rune-detail">
        <div className="rd-head">
          <img src={`/runeicons/${n.icon}.png`} alt="" />
          <div>
            <b>{n.name}</b>
            <span className="muted">
              {" "}nível {n.level}/{n.max}
              {!n.unlocked && " · bloqueada"}
            </span>
          </div>
        </div>
        {n.gain && (
          <p className="rd-gain">
            próxima compra: <b>{runeStatPt(n.stat, n.nextValue ?? 0)}</b>
            {n.gain.label && n.gain.pct != null && (
              <> → <b className={n.gain.kind === "combate" ? "v-exp" : "v-gold"}>{n.gain.label}</b></>
            )}
          </p>
        )}
        {n.path && n.path.steps.length > 0 && (
          <div className="rd-path">
            <span className="rd-path-title">rota pra destravar</span>
            {n.path.steps.map((s, i) => (
              <button className="rd-step" key={i} onClick={() => onPick(s.key)}>
                <img src={`/runeicons/${s.icon}.png`} alt="" />
                <span>
                  {s.name} <em>nv{s.fromLevel}→{s.toLevel}</em>
                </span>
                <b>{fmt(s.cost)} <em className="gold-unit">gold</em></b>
              </button>
            ))}
            <div className="rd-step total">
              <span>total pra liberar</span>
              <b className="v-gold">{fmt(n.path.chainCost)} <em className="gold-unit">gold</em></b>
            </div>
          </div>
        )}
        <table className="mini">
          <thead>
            <tr><th>nv</th><th>efeito</th><th>custo</th></tr>
          </thead>
          <tbody>
            {n.perLevel.map((l) => (
              <tr key={l.level} className={l.level === n.level + 1 ? "is-current" : ""}>
                <td className={l.level <= n.level ? "v-gold" : "muted"}>
                  {l.level <= n.level ? "✓ " : ""}{l.level}
                </td>
                <td>{runeStatPt(n.stat, l.value ?? 0)}</td>
                <td>{l.cost != null ? fmt(l.cost) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Flow({ runes, sel, setSel }) {
  const { setCenter } = useReactFlow();

  const byKey = useMemo(
    () => Object.fromEntries(runes.nodes.map((n) => [n.key, n])),
    [runes.nodes]
  );
  // ranking 1º/2º/3º por tipo: 1º pisca forte, 2º/3º brilham menos
  const rankMap = useMemo(() => {
    const m = {};
    runes.recommendations.combate.slice(0, 3).forEach((r, i) => {
      if (!m[r.key]) m[r.key] = { kind: "c", rank: i + 1 };
    });
    runes.recommendations.farm.slice(0, 3).forEach((r, i) => {
      if (!m[r.key]) m[r.key] = { kind: "f", rank: i + 1 };
    });
    return m;
  }, [runes]);

  // rota de desbloqueio do nó selecionado: ancestrais até a raiz + níveis exigidos
  const { pathSet, needMap } = useMemo(() => {
    const selNode = sel != null ? byKey[sel] : null;
    if (!selNode || selNode.unlocked) return { pathSet: new Set(), needMap: {} };
    const parent = {};
    for (const e of runes.edges) parent[e.to] = e.from;
    const set = new Set([selNode.key]);
    let cur = selNode.key;
    while (parent[cur] != null) {
      cur = parent[cur];
      set.add(cur);
    }
    const need = {};
    for (const s of selNode.path?.steps || []) need[s.key] = s.toLevel;
    return { pathSet: set, needMap: need };
  }, [sel, byKey, runes.edges]);

  // posições EXATAS da wiki (x,y são centros; tile 48 -> desloca metade)
  const rfNodes = useMemo(
    () =>
      runes.nodes.map((n) => ({
        id: String(n.key),
        type: "rune",
        position: { x: (n.x ?? 0) - TILE / 2, y: (n.y ?? 0) - TILE / 2 },
        data: {
          n,
          selected: sel === n.key,
          rank: rankMap[n.key],
          inPath: pathSet.has(n.key),
          needLevel: needMap[n.key],
        },
        draggable: false,
        connectable: false,
      })),
    [runes.nodes, sel, rankMap, pathSet, needMap]
  );

  const rfEdges = useMemo(
    () =>
      runes.edges.map((e) => {
        const inPath = pathSet.has(e.from) && pathSet.has(e.to);
        const both = byKey[e.from]?.owned && byKey[e.to]?.owned;
        const open = byKey[e.to]?.unlocked;
        return {
          id: e.from + ">" + e.to,
          source: String(e.from),
          target: String(e.to),
          type: "straight",
          className:
            "redge " + (inPath ? "path" : both ? "on" : open ? "open" : "off"),
        };
      }),
    [runes.edges, byKey, pathSet]
  );

  const pick = useCallback(
    (key) => {
      setSel(key);
      const n = byKey[key];
      if (n && n.x != null) setCenter(n.x, n.y, { zoom: 1.15, duration: 500 });
    },
    [byKey, setCenter, setSel]
  );

  return (
    <div className="page runes-page">
      <div className="main-col">
        <section className="sec flow-sec">
          <div className="sec-head">
            <h2>Árvore de runas</h2>
            <div className="flow-legend">
              <span><i className="lg maxed" /> máxima</span>
              <span><i className="lg owned" /> comprada</span>
              <span><i className="lg buyable" /> disponível</span>
              <span><i className="lg locked" /> bloqueada</span>
              <span><i className="lg rank-c" /> 1º combate</span>
              <span><i className="lg rank-f" /> 1º farm</span>
              <span><i className="lg path" /> rota</span>
              <span className="muted">gold: <b className="v-gold">{fmt(runes.gold)}</b></span>
            </div>
          </div>
          <div className="flow-wrap">
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              nodeTypes={nodeTypes}
              onNodeClick={(_, n) => pick(Number(n.id))}
              onPaneClick={() => setSel(null)}
              fitView
              fitViewOptions={{ padding: 0.06 }}
              minZoom={0.15}
              maxZoom={2.2}
              panOnScroll
              zoomOnScroll={false}
              nodesDraggable={false}
              nodesConnectable={false}
            >
              <Controls showInteractive={false} />
              <MiniMap
                pannable
                zoomable
                nodeStrokeWidth={6}
                nodeColor={(n) => {
                  const s = nodeState(n.data.n);
                  return s === "maxed" ? "#f5b13d"
                    : s === "owned" ? "#c08a2d"
                    : s.startsWith("buyable") ? "#38d9cf" : "#333d4f";
                }}
                maskColor="rgba(7,9,14,.72)"
                bgColor="#0a0d14"
              />
            </ReactFlow>
          </div>
        </section>
      </div>

      <aside className="rail">
        {sel != null && byKey[sel] && <RuneDetails n={byKey[sel]} onPick={pick} />}
        <RecList
          title="Rank — combate"
          recs={runes.recommendations.combate.slice(0, 3)}
          onPick={pick}
          kind="c"
        />
        <RecList
          title="Rank — farm"
          recs={runes.recommendations.farm.slice(0, 3)}
          onPick={pick}
          kind="f"
        />
        <RecList
          title="Vale destravar (rota)"
          recs={runes.recommendations.destravar}
          onPick={pick}
          showSteps
        />
      </aside>
    </div>
  );
}

export default function RunesPage({ runes }) {
  const [sel, setSel] = useState(null);
  if (!runes) return <div className="loading">carregando runas…</div>;
  return (
    <ReactFlowProvider>
      <Flow runes={runes} sel={sel} setSel={setSel} />
    </ReactFlowProvider>
  );
}
