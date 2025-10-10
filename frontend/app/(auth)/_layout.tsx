import { Stack } from "expo-router";
export default function AuthLayout() {
  return (
    <Stack>
      <Stack.Screen name="login" options={{ title: "로그인" }} />
      <Stack.Screen name="register" options={{ title: "회원가입" }} />
    </Stack>
  );
}
