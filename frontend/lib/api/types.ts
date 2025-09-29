export type Currency = "KRW" | "USD";

export type PortfolioSnapshot = {
  currency: Currency;
  totalEquity: string;   // "123456789.12"
  cash: string;
  pnlDay: string;        // 일손익
  pnlDayPct: string;     // "0.0123" => 1.23%
  updatedAt: string;     // ISO string
};

export type Position = {
  symbol: string;        // "005930.KS" 등
  name?: string;         // "삼성전자"
  qty: string;           // 수량
  avgPrice: string;      // 평균단가
  lastPrice: string;     // 현재가
  pnl: string;           // 평가손익
  pnlPct: string;        // 수익률
};

export type Ticker = { symbol: string; price: string; ts: number };

export type ChartDatum = {
  timestamp: number; // Unix timestamp in milliseconds
  open: number;
  high: number;
  low: number;
  close: number;
};

export type ChartProps = {
  data: ChartDatum[];
}