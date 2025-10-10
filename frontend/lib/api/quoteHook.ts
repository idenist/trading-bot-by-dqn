// lib/api/quoteHook.ts
import { useEffect, useState } from 'react';
import { getQuote } from './quote';

export function useQuote(symbol: string, intervalMs = 2000) {
  const [quote, setQuote] = useState<ReturnType<typeof Object> | any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;  // ✅ 핵심

    async function tick() {
      try {
        const q = await getQuote(symbol);
        if (!alive) return;
        setQuote(q);
        setLoading(false);
      } catch {}
      timer = setTimeout(tick, intervalMs);
    }

    setLoading(true);
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [symbol, intervalMs]);

  return { quote, loading };
}
