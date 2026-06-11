import React from "react";

export default function Coach({ paragraphs }) {
  if (!paragraphs?.length) return null;
  const [first, ...rest] = paragraphs;
  return (
    <div className="card coach">
      <h2>Copilot recomenda</h2>
      <p className="coach-lead">{first}</p>
      <ul className="coach-list">
        {rest.map((p, i) => (
          <li key={i}>{p}</li>
        ))}
      </ul>
    </div>
  );
}
