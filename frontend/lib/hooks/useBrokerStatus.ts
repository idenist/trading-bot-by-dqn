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
      } catch (e: any) {
        if (!alive) return;
        // 실패해도 최소 상태는 내려줘서 UI가 진행되게
        setData(prev => prev ?? { broker: "kiwoom", status: "DISCONNECTED", message: e?.message });
      } finally {
        if (alive) setLoading(false);           // ✅ 성공/실패 모두에서 로딩 해제
        timer = setTimeout(tick, intervalMs);   // 다음 폴링 예약
      }
    }

    setLoading(true);
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [intervalMs]);

  return { status: data, loading };
}
