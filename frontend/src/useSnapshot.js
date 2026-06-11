import { useEffect, useRef, useState } from "react";

const POLL_MS = 2000;

export function useSnapshot() {
  const [data, setData] = useState(null);
  const [online, setOnline] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const res = await fetch("/api/snapshot");
        const d = await res.json();
        if (alive) {
          setData(d);
          setOnline(true);
        }
      } catch {
        if (alive) setOnline(false);
      }
      if (alive) timer.current = setTimeout(poll, POLL_MS);
    }
    poll();
    return () => {
      alive = false;
      clearTimeout(timer.current);
    };
  }, []);

  return { data, online };
}
