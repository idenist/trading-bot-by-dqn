// import { api } from "./client";

// export type BrokerStatus = {
//   broker: string;
//   status: "CONNECTED" | "DISCONNECTED" | "ERROR";
//   message?: string;
// };

// export async function postBrokerConnect(appKey: string, secretKey: string) {
//   const { data } = await api.post<BrokerStatus>("/broker/kiwoom/connect", {
//     app_key: appKey,
//     secret_key: secretKey,
//   });
//   return data;
// }

// export async function getBrokerStatus() {
//   const { data } = await api.get<BrokerStatus>("/broker/kiwoom/status");
//   return data;
// }
