// lib/api/stocks.ts
import { api } from "./client";

export type Stock = {
  symbol: string;
  name: string;
  market?: string;
};

export type StockInfo = {
  symbol: string;
  name: string;
  price: number;
  changePct: number;
  volume?: number;
  marketCap?: number;
};

// 주식 검색
export const searchStocks = async (query: string): Promise<Stock[]> => {
  try {
    const response = await api.get(`/stocks/search`, {
      params: { q: query }
    });
    return response.data;
  } catch (error) {
    console.error("주식 검색 실패:", error);
    return [];
  }
};

// 주식 정보 조회
export const getStockInfo = async (symbol: string): Promise<StockInfo> => {
  try {
    const response = await api.get(`/stocks/${symbol}`);
    return response.data;
  } catch (error) {
    console.error("주식 정보 조회 실패:", error);
    throw error;
  }
};

// 모든 주식 목록 조회
export const getAllStocks = async (): Promise<Stock[]> => {
  try {
    const response = await api.get(`/stocks`);
    return response.data;
  } catch (error) {
    console.error("주식 목록 조회 실패:", error);
    return [];
  }
};
