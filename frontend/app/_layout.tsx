// app/_layout.tsx
import 'react-native-gesture-handler';        // ← 권장: 가장 먼저
import 'react-native-reanimated';

import React, { useEffect, useState } from 'react';
import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack, Slot, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { useColorScheme } from '@/hooks/use-color-scheme';
import { getAccessToken } from '@/lib/api/auth';

export const unstable_settings = {
  anchor: '(tabs)',
};

export default function RootLayout() {
  const colorScheme = useColorScheme();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  // useEffect(() => {
  //   (async () => {
  //     try {
  //       const token = await getAccessToken();
  //       if (!token) {
  //         // 비로그인 → auth 스택으로
  //         router.replace('/(auth)/login');
  //       }
  //     } finally {
  //       setReady(true);
  //     }
  //   })();
  // }, []);

  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      {/* ready 되기 전엔 빈 화면로딩 (스플래시/로더를 쓰고 싶으면 여기 교체) */}
      {ready ? (
        <Stack>
          {/* 탭 루트 */}
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          {/* 모달 라우트(필요 시 유지) */}
          <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
          {/* auth 그룹은 별도 (/(auth)/_layout.tsx에서 헤더/타이틀 관리) */}
        </Stack>
      ) : (
        <Slot /> /* <- expo-router 권장 패턴: 준비 전 children 자리 */
      )}

      <StatusBar style="auto" />
    </ThemeProvider>
  );
}
