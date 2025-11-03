import { useEffect, useState } from 'react';
import { getQuote } from './quote';

type QuoteData = {
  symbol: string;
  name?: string;
  price: number;
  changePct: number;
};

export function useQuote(symbol: string, intervalMs = 2000) {
  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) return;
    
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;

    async function tick() {
      try {
        const q = await getQuote(symbol);
        if (!alive) return;
        
        setQuote(q);
        setLoading(false);
        setError(null);
      } catch (err) {
        if (!alive) return;
        
        console.error('Quote polling error:', err);
        setError(err instanceof Error ? err.message : 'Quote fetch failed');
        setLoading(false);
      }
      
      // 다음 폴링 예약
      if (alive) {
        timer = setTimeout(tick, intervalMs);
      }
    }

    setLoading(true);
    setError(null);
    tick();

    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [symbol, intervalMs]);

  return { quote, loading, error };
}
