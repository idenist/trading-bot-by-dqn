import { api } from '@/lib/api/client';

export type QuoteDTO = {
  symbol: string;
  name?: string;
  price: number;
  prevClose?: number;
  changePct?: string;
  timestamp?: string;
};

export async function getQuote(symbol: string): Promise<{
  symbol: string; 
  name?: string; 
  price: number; 
  changePct: number;
}> {
  try {
    const { data } = await api.get<QuoteDTO>(`/quote/${encodeURIComponent(symbol)}`);
    
    // changePct 계산 (서버에서 오거나 계산)
    let changePct = 0;
    if (data.changePct) {
      changePct = parseFloat(data.changePct);
    } else if (data.prevClose && data.prevClose > 0) {
      changePct = (data.price / data.prevClose) - 1;
    }
    
    return {
      symbol: data.symbol,
      name: data.name,
      price: parseFloat(data.price.toString()) || 0,
      changePct: changePct
    };
  } catch (error) {
    console.error(`Quote fetch error for ${symbol}:`, error);
    // 에러 시 기본값 반환
    return {
      symbol: symbol,
      name: undefined,
      price: 0,
      changePct: 0
    };
  }
}
