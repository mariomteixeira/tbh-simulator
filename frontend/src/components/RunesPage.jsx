import React, { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { fmt } from "../format.js";
import { runeStatPt } from "../statNames.js";

const COL_W = 215; // distância horizontal entre profundidades
const ROW_H = 86;  // distância vertical entre folhas

/* tidy tree: folhas em linhas sequenciais, pai centrado nos filhos */
function layoutTree(nodes, edges) {
  const children = {};
  const hasParent = new Set();
  for (const e of edges) {
    (children[e.from] ??= []).push(e.to);
    hasParent.add(e.to);
  }
  const roots = nodes.map((n) => n.key).filter((k) => !hasParent.has(k));
  const pos = {};
  let leaf = 0;
  const place = (k, depth) => {
    const kids = children[k] || [];
    if (!kids.length) {
      pos[k] = { x: depth * COL_W, y: leaf++ * ROW_H };
      return pos[k].y;
    }
    const ys = kids.map((c) => place(c, depth + 1));
    const y = (Math.min(...ys) + Math.max(...ys)) / 2;
    pos[k] = { x: depth * COL_W, y };
    return y;
  };
  for (const r of roots) {
    place(r, 0);
    leaf += 1; // respiro entre as duas árvores
  }
  return pos;
}

function nodeState(n) {
  if (n.maxed) return "maxed";
  if (n.owned) return "owned";
  if (n.unlocked) return n.gain?.affordable ? "buyable afford" : "buyable";
  return "locked";
}

function RuneNode({ data }) {
  const n = data.n;
  return (
    <div className={"rune-node " + nodeState(n) + (data.selected ? " sel" : "") + (data.starred ? " star" : "")}>
      <Handle type="target" position={Position.Left} />
      <img src={`/runeicons/${n.icon}.png`} alt="" draggable={false} />
      <div className="rn-info">
        <span className="rn-name">{n.name}</span>
        <span className="rn-lv">
          {n.level}/{n.max}
          {!n.maxed && n.unlocked && n.nextCost != null && (
            <em> · {fmt(n.nextCost)}g</em>
          )}
        </span>
      </div>
      {data.starred && <span className="rn-badge">★</span>}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { rune: RuneNode };

function RecList({ title, recs, gold, onPick }) {
  if (!recs?.length) return null;
  return (
    <div>
      <h3>{title}</h3>
      <div className="rec-list">
        {recs.map((r) => (
          <button className="rec" key={r.key + "-" + r.level} onClick={() => onPick(r.key)}>
            <img src={`/runeicons/${r.icon}.png`} alt="" />
            <span className="rec-body">
              <span className="rec-name">
                {r.name} <em>nv {r.level}</em>
              </span>
              <span className="rec-gain">{r.label}</span>
            </span>
            <span className={"rec-cost" + (r.affordable ? " ok" : "")}>
              {fmt(r.cost)}g
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Flow({ runes, sel, setSel }) {
  const { setCenter } = useReactFlow();
  const starred = useMemo(() => {
    const s = new Set();
    for (const r of runes.recommendations.combate.slice(0, 1)) s.add(r.key);
    for (const r of runes.recommendations.farm.slice(0, 1)) s.add(r.key);
    return s;
  }, [runes]);

  const pos = useMemo(
    () => layoutTree(runes.nodes, runes.edges),
    [runes.nodes, runes.edges]
  );
  const byKey = useMemo(
    () => Object.fromEntries(runes.nodes.map((n) => [n.key, n])),
    [runes.nodes]
  );

  const rfNodes = useMemo(
    () =>
      runes.nodes.map((n) => ({
        id: String(n.key),
        type: "rune",
        position: pos[n.key] || { x: 0, y: 0 },
        data: { n, selected: sel === n.key, starred: starred.has(n.key) },
        draggable: false,
        connectable: false,
      })),
    [runes.nodes, pos, sel, starred]
  );
  const rfEdges = useMemo(
    () =>
      runes.edges.map((e) => {
        const both = byKey[e.from]?.owned && byKey[e.to]?.owned;
        const open = byKey[e.to]?.unlocked;
        return {
          id: e.from + ">" + e.to,
          source: String(e.from),
          target: String(e.to),
          type: "smoothstep",
          label: e.req > 1 ? "nv " + e.req : undefined,
          className: "redge " + (both ? "on" : open ? "open" : "off"),
        };
      }),
    [runes.edges, byKey]
  );

  const pick = useCallback(
    (key) => {
      setSel(key);
      const p = pos[key];
      if (p) setCenter(p.x + 80, p.y + 20, { zoom: 1, duration: 500 });
    },
    [pos, setCenter, setSel]
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
              <span className="muted">★ melhor compra · gold: <b className="v-gold">{fmt(runes.gold)}</b></span>
            </div>
          </div>
          <div className="flow-wrap">
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              nodeTypes={nodeTypes}
              onNodeClick={(_, n) => pick(Number(n.id))}
              fitView
              fitViewOptions={{ padding: 0.15, maxZoom: 0.9 }}
              minZoom={0.08}
              maxZoom={1.6}
              panOnScroll
              zoomOnScroll={false}
              nodesDraggable={false}
              nodesConnectable={false}
              proOptions={{ hideAttribution: false }}
            >
              <Background gap={42} size={1} color="#1b2433" />
              <Controls showInteractive={false} />
              <MiniMap
                pannable
                zoomable
                nodeColor={(n) => {
                  const s = nodeState(n.data.n);
                  return s === "maxed" ? "#f5b13d" : s === "owned" ? "#9a7a35"
                    : s.startsWith("buyable") ? "#38d9cf" : "#27303f";
                }}
                maskColor="rgba(7,9,14,.78)"
                bgColor="#0a0d14"
              />
            </ReactFlow>
          </div>
        </section>
      </div>

      <aside className="rail">
        {sel != null && byKey[sel] && <RuneDetails n={byKey[sel]} />}
        <RecList
          title="Melhor compra — combate"
          recs={runes.recommendations.combate}
          onPick={pick}
        />
        <RecList
          title="Melhor compra — farm"
          recs={runes.recommendations.farm}
          onPick={pick}
        />
        <p className="muted small">
          Ganhos de combate são recalculados com o seu time real; ganhos de farm
          valem para o estágio atual. Custo em gold; ★ marca a melhor compra de
          cada tipo. Ícones: taskbarhero.wiki (fan-made).
        </p>
      </aside>
    </div>
  );
}

function RuneDetails({ n }) {
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
              {!n.unlocked && " · bloqueada (pai precisa nv " + n.req + ")"}
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

export default function RunesPage({ runes }) {
  const [sel, setSel] = useState(null);
  if (!runes) return <div className="loading">carregando runas…</div>;
  return (
    <ReactFlowProvider>
      <Flow runes={runes} sel={sel} setSel={setSel} />
    </ReactFlowProvider>
  );
}
