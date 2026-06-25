import React, { useState } from "react";
import { gradeOf, gearPt } from "../grades.js";

export const typeLabel = (e) =>
  e.type === "GEAR" ? gearPt(e.gear) || e.gear : e.type === "MATERIAL" ? "Material" : e.type;

export default function ItemIcon({ e, size = 40 }) {
  const [bad, setBad] = useState(false);
  const g = gradeOf(e.grade);
  if (bad || !e.key)
    return (
      <span className="cube-ico-fallback" style={{ width: size, height: size, color: g.c }}>
        {(typeLabel(e) || "").slice(0, 2)}
      </span>
    );
  return (
    <img
      className="cube-ico"
      style={{ width: size, height: size }}
      src={`/itemicon/${e.key}.png`}
      alt=""
      loading="lazy"
      onError={() => setBad(true)}
    />
  );
}
