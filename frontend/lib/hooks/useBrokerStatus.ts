import { useEffect, useState } from "react";
import { getBrokerStatus, type BrokerStatus } from "@/lib/api/broker";

export function useBrokerStatus(intervalMs = 5000) {
  const [data, setData] = useState<BrokerStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;

    async function tick() {
      try {
        const s = await getBrokerStatus();
        if (!alive) return;
        setData(s);
        setLoading(false);
      } catch {
        /* ignore */
      }
      timer = setTimeout(tick, intervalMs);
    }

    setLoading(true);
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [intervalMs]);

  return { status: data, loading };
}
