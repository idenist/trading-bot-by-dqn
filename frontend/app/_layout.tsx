// app/_layout.tsx
import 'react-native-gesture-handler';        // ← 권장: 가장 먼저
import 'react-native-reanimated';

import React, { useEffect } from 'react';
import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack, useRouter, usePathname } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { useColorScheme } from '@/hooks/use-color-scheme';
import { getAccessToken } from '@/lib/api/auth';

export const unstable_settings = {
  anchor: '(tabs)',
};

export default function RootLayout() {
  const colorScheme = useColorScheme();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    (async () => {
      try {
        const token = await getAccessToken();
        if (!token) {
          // 비로그인 시, 로그인/회원가입 페이지가 아니면 로그인 페이지로 리디렉션
          if (pathname !== '/login' && pathname !== '/register') {
            router.replace('/login');
          }
        }
      } catch (e) {
        console.error(e);
      }
    })();
  }, [pathname]);

  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      <Stack>
        {/* 탭 루트 */}
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        {/* 모달 라우트(필요 시 유지) */}
        <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
        {/* auth 그룹은 별도 (/(auth)/_layout.tsx에서 헤더/타이틀 관리) */}
        <Stack.Screen name="(auth)" options={{ headerShown: false}} />
      </Stack>

      <StatusBar style="auto" />
    </ThemeProvider>
  );
}