// lib/hooks/useBrokerStatus.ts
import { useEffect, useState } from "react";
import { getApiKeys } from "@/lib/api/auth";
import { getAccessToken } from "@/lib/storage"; // 경로는 너 프로젝트에 맞춰

export function useBrokerStatus(intervalMs = 5000) {
  const [status, setStatus] = useState<"CONNECTED" | "DISCONNECTED">("DISCONNECTED");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;

    async function tick() {
      try {
        const token = await getAccessToken();
        if (!alive) return;

        if (!token) {
          setStatus("DISCONNECTED");
          return; // ✅ 토큰 없으면 API 호출 금지
        }

        const keys = await getApiKeys(); // 여기까지 오면 인터셉터가 Authorization 붙임
        if (!alive) return;
        setStatus(keys?.appkey && keys?.secretkey ? "CONNECTED" : "DISCONNECTED");
      } catch {
        if (!alive) return;
        setStatus("DISCONNECTED");
      } finally {
        if (alive) setLoading(false);
        timer = setTimeout(tick, intervalMs);
      }
    }

    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [intervalMs]);

  return { status, loading };
}
