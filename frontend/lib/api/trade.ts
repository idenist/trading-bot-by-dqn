// frontend/lib/api/trade.ts
import { api } from "./client";

export type OrderSide = "BUY" | "SELL";
export type OrderType = "MARKET" | "LIMIT";

export async function placeOrderApi(params: {
  symbol: string;
  side: OrderSide;
  type: OrderType;
  price: number;
  qty: number;
}) {
  const res = await api.post("/order", params);
  return res.data as {
    success: boolean;
    orderId: string;
    message: string;
  };
}

export async function startAutoTrade(stocks: string[], amountPerStock: number) {
  const res = await api.post("/auto-trade/start", {
    stocks,
    amount_per_stock: amountPerStock,
  });
  return res.data as {
    success: boolean;
    message: string;
    stocks: string[];
    amount_per_stock: number;
  };
}

export async function stopAutoTrade() {
  const res = await api.post("/auto-trade/stop");
  return res.data as { success: boolean; message: string };
}

export type AutoTradeStatus = {
  running: boolean;
  stocks?: string[];
  amount_per_stock?: number;
};

export async function getAutoTradeStatus() {
  const res = await api.get("/auto-trade/status");
  return res.data as AutoTradeStatus;
}
