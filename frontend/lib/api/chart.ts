// lib/api/chart.ts
import { api } from "./client";
import type { ChartDatum } from "./types";

export const getChartData = (
  symbol: string,
  interval: "1D" | "1W" | "1M",
  amount: number,
): Promise<ChartDatum[]> => {
  return api
    .post<ChartDatum[]>("/chart", {
      symbol,
      interval,
      amount,
      base_date: "", // 빈 문자열 → 백엔드에서 오늘로 처리
    })
    .then((r) => r.data ?? []);
};
