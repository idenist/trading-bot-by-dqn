import React from "react";
import { SafeAreaView, View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Alert } from "react-native";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import FormInput from "@/components/ui/FormInput";
import { loginSchema, type LoginInput } from "@/lib/validation/auth";
import { loginApi } from "@/lib/api/auth";
import { useRouter, Link } from "expo-router";

export default function LoginScreen() {
  const router = useRouter();
  const { control, handleSubmit, formState: { isSubmitting } } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (v: LoginInput) => {
    try {
      await loginApi(v);
      router.replace("/"); // 로그인 성공 후 홈으로
    } catch (e: any) {
      Alert.alert("로그인 실패", e?.response?.data?.detail ?? "이메일 또는 비밀번호를 확인하세요.");
    }
  };

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.card}>
        <Text style={s.title}>로그인</Text>

        <FormInput control={control} name="email" label="이메일" placeholder="you@example.com" keyboardType="email-address" />
        <FormInput control={control} name="password" label="비밀번호" secureTextEntry />

        <TouchableOpacity style={[s.btn, isSubmitting && { opacity: 0.6 }]} onPress={handleSubmit(onSubmit)} disabled={isSubmitting}>
          {isSubmitting ? <ActivityIndicator color="#fff" /> : <Text style={s.btnTx}>로그인</Text>}
        </TouchableOpacity>

        <View style={s.row}>
          <Text style={{ color: "#6b7280" }}>계정이 없으신가요?</Text>
          <Link href="/(auth)/register" asChild><TouchableOpacity><Text style={s.link}> 회원가입</Text></TouchableOpacity></Link>
        </View>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, justifyContent: "center", padding: 16, backgroundColor: "#fff" },
  card: { borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 16, padding: 16 },
  title: { fontSize: 22, fontWeight: "800", marginBottom: 12 },
  btn: { backgroundColor: "#111827", borderRadius: 12, paddingVertical: 14, alignItems: "center", marginTop: 6 },
  btnTx: { color: "#fff", fontWeight: "800", fontSize: 16 },
  row: { flexDirection: "row", marginTop: 12, justifyContent: "center" },
  link: { color: "#2563eb", fontWeight: "700" },
});
