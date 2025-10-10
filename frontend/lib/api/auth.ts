import axios from "axios";
import { getItem, setItem, deleteItem } from "@/lib/storage";

const api = axios.create({ baseURL: process.env.EXPO_PUBLIC_API_BASE });

export type AuthResp = { accessToken: string; refreshToken?: string };

export async function loginApi(body:{email:string; password:string}) {
  const { data } = await api.post<AuthResp>("/auth/login", body);
  await setItem("accessToken", data.accessToken);
  if (data.refreshToken) await setItem("refreshToken", data.refreshToken);
  return data;
}

export async function registerApi(body: { email: string; password: string }): Promise<void> {
  await api.post("/auth/register", body);
}

export async function logoutApi() {
  await deleteItem("accessToken");
  await deleteItem("refreshToken");
}

export async function getAccessToken() {
  return getItem("accessToken");
}