import axios from "axios";

export type Position = {
  symbol: string;
  name?: string;
  qty: string;
  avgPrice: string;
  lastPrice: string;
  pnl: string;
  pnlPct: string; // "0.0123" → 1.23%
};

const api = axios.create({ baseURL: process.env.EXPO_PUBLIC_API_BASE });

export const getPositions = async () =>
  (await api.get<Position[]>("/positions")).data;
