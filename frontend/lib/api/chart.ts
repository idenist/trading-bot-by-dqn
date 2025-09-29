import { api } from "./client";

function getChartData(symbol: string, interval: string, base_date: string, amount: number) {
    return api.post<any>(`/chart`, {
         symbol, base_date, interval, amount 
    }).then(r => r.data);
}

export { getChartData };

