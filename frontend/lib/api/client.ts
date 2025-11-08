// lib/api/client.ts
import axios from "axios";
import { router } from "expo-router";
import { getAccessToken } from "./auth";
import { deleteItem } from "../storage";

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
        config.headers = config.headers ?? {};
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

// 응답 인터셉터 - 401 에러 처리
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      console.log("토큰 만료, 재로그인 필요");
      // 토큰 삭제
      await deleteItem("accessToken");
      await deleteItem("refreshToken");
      // 로그인 페이지로 리디렉션
      router.replace("/(auth)/login");
    }
    if (error.response?.status === 403) {
      console.log("토큰 미발급");
      // 로그인 페이지로 리디렉션
      router.replace("/(auth)/login");
    }
    return Promise.reject(error);
  }
);