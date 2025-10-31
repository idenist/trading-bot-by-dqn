// lib/api/client.ts
import axios from "axios";
import { getAccessToken } from "./auth";

export const api = axios.create({
  baseURL: process.env.EXPO_PUBLIC_API_BASE,
  timeout: 15000,
});

// 요청 인터셉터 - 토큰 추가
api.interceptors.request.use(
  async (config) => {
    try {
      const token = await getAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (error) {
      console.error("토큰 가져오기 실패:", error);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);
