import React from "react";
import { SafeAreaView, View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Alert } from "react-native";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import FormInput from "@/components/ui/FormInput";
import { registerSchema, type RegisterInput } from "@/lib/validation/auth";
import { registerApi } from "@/lib/api/auth";
import { useRouter, Link } from "expo-router";

export default function RegisterScreen() {
  const router = useRouter();
  const { control, handleSubmit, formState: { isSubmitting } } = useForm<RegisterInput>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: "", password: "", confirm: "" },
  });

  const onSubmit = async (v: RegisterInput) => {
    try {
      await registerApi({ email: v.email, password: v.password });
      Alert.alert("완료", "회원가입이 완료되었습니다. 로그인해주세요.");
      router.replace("/(auth)/login");
    } catch (e: any) {
      Alert.alert("회원가입 실패", e?.response?.data?.detail ?? "잠시 후 다시 시도해주세요.");
    }
  };

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.card}>
        <Text style={s.title}>회원가입</Text>

        <FormInput control={control} name="email" label="이메일" placeholder="you@example.com" keyboardType="email-address" />
        <FormInput control={control} name="password" label="비밀번호" secureTextEntry />
        <FormInput control={control} name="confirm" label="비밀번호 확인" secureTextEntry />

        <TouchableOpacity style={[s.btn, isSubmitting && { opacity: 0.6 }]} onPress={handleSubmit(onSubmit)} disabled={isSubmitting}>
          {isSubmitting ? <ActivityIndicator color="#fff" /> : <Text style={s.btnTx}>회원가입</Text>}
        </TouchableOpacity>

        <View style={s.row}>
          <Text style={{ color: "#6b7280" }}>이미 계정이 있으신가요?</Text>
          <Link href="/login" asChild><TouchableOpacity><Text style={s.link}> 로그인</Text></TouchableOpacity></Link>
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
