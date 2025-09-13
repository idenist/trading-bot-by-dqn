import axios from "axios";

// .env 설정: EXPO_PUBLIC_API_BASE=https://your-fastapi.example.com
export const api = axios.create({
  baseURL: process.env.EXPO_PUBLIC_API_BASE,
  timeout: 15000,
});

// 요청/응답 인터셉터(토큰 등)
api.interceptors.request.use(async (config) => {
  // TODO: 토큰 보관 시 MMKV에서 꺼내기
  // const token = ...
  // if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
