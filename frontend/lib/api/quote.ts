import { api } from '@/lib/api/client';

export type QuoteDTO = {
  symbol: string;
  name?: string;
  price: number;
  prevClose?: number;
};

export async function getQuote(symbol: string): Promise<{symbol:string; name?:string; price:number; changePct:number}> {
  const { data } = await api.get<QuoteDTO>(`/quote/${encodeURIComponent(symbol)}`);
  const changePct = data.prevClose ? data.price / data.prevClose - 1 : 0;
  return { ...data, changePct };
}
