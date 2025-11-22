import { api } from "@/lib/api/client";
import { getItem, setItem, deleteItem } from "@/lib/storage";
import * as SecureStore from "expo-secure-store";
import { API_BASE_URL } from "./client"; // 너가 쓰는 베이스 URL 모듈 이름에 맞게

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
  try {
    await api.get("/auth/logout");
  } catch (error) {
    console.error("Failed to logout from server", error);
  } finally {
    await deleteItem("accessToken");
    await deleteItem("refreshToken");
  }
}

export async function getAccessToken() {
  return getItem("accessToken");
}

export interface APIKeyData {
  appkey: string;
  secretkey: string;
  mock: boolean;
}

export async function getApiKeys(): Promise<APIKeyData | null> {
  const res = await api.get<APIKeyData>("/auth/get_api_keys/");
  return res.data;
}

export async function setApiKeys(data: APIKeyData): Promise<void> {
  await api.post("/auth/set_api_keys/", data);
}

export async function deleteApiKeys(): Promise<void> {
  await api.delete("/auth/delete_api_keys/");
}

export async function logout() {
  const token = await SecureStore.getItemAsync("accessToken");

  if (token) {
    try {
      await fetch(`${API_BASE_URL}/auth/logout/`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    } catch (e) {
      console.warn("logout request failed:", e);
      // 서버 실패해도 로컬 토큰은 지워서 강제 로그아웃
    }
  }

  await SecureStore.deleteItemAsync("accessToken");
}
