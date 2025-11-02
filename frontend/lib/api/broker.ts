import axios from "axios";

export type LinkStatus = "DISCONNECTED" | "WAITING_LOGIN" | "CONNECTED" | "ERROR";
export type BrokerStatus = {
  broker: "kiwoom";
  status: LinkStatus;
  message?: string;
  sessionId?: string;
  accounts?: Array<{ accountNo: string; name?: string }>;
};

const api = axios.create({ baseURL: process.env.EXPO_PUBLIC_API_BASE });

export const getBrokerStatus = async () =>
  (await api.get<BrokerStatus>("/broker/kiwoom/status")).data;

export const startLink = async () =>
  (await api.post<BrokerStatus>("/broker/kiwoom/connect")).data;

export const disconnect = async () =>
  (await api.post<BrokerStatus>("/broker/kiwoom/disconnect")).data;

export const getAccounts = async () =>
  (await api.get<BrokerStatus>("/broker/kiwoom/accounts")).data;

export const setDefaultAccount = async (accountNo: string) => {
  await api.post("/broker/kiwoom/select-account", { accountNo });
};
