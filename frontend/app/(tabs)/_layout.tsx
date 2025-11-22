import { Stack, useRouter } from "expo-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React, { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Text } from "react-native";
import { GestureHandlerRootView } from 'react-native-gesture-handler';

const queryClient = new QueryClient();

function ProtectedLayout() {
  const { isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated === false) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  if (isAuthenticated === null) {
    return <Text>Loading...</Text>; // Or a loading spinner
  }

  if (isAuthenticated === false) {
    return null; 
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <ProtectedLayout />
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}