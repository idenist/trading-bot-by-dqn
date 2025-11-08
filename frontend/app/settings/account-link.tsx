import React, { useState, useEffect } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, SafeAreaView, ScrollView } from "react-native";
import { getApiKeys, setApiKeys, deleteApiKeys } from "@/lib/api/auth"; // 아래 2️⃣에 추가할 함수들
import { useRouter } from "expo-router";

export default function AccountLinkScreen() {
  const [appKey, setAppKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [mock, setMock] = useState(true);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  // 기존에 저장된 키 가져오기
  useEffect(() => {
    (async () => {
      try {
        const res = await getApiKeys();
        if (res) {
          setAppKey(res.appkey ?? "");
          setSecretKey(res.secretkey ?? "");
          setMock(res.mock ?? true);
        }
      } catch (e) {
        console.log("Failed to load API keys:", e);
      }
    })();
  }, []);

  const onSave = async () => {
    if (!appKey || !secretKey) {
      Alert.alert("입력 오류", "App Key와 Secret Key를 모두 입력해주세요.");
      return;
    }
    setLoading(true);
    try {
      await setApiKeys({ appkey: appKey, secretkey: secretKey, mock });
      Alert.alert("완료", "API 키가 저장되었습니다.", [
        { text: "확인", onPress: () => router.back() },
      ]);
    } catch (e) {
      console.error(e);
      Alert.alert("오류", "API 키 저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const onDelete = async () => {
    Alert.alert("확인", "API 키를 삭제하시겠습니까?", [
      { text: "취소", style: "cancel" },
      {
        text: "삭제",
        style: "destructive",
        onPress: async () => {
          try {
            await deleteApiKeys();
            setAppKey("");
            setSecretKey("");
            Alert.alert("삭제 완료", "API 키가 삭제되었습니다.");
          } catch {
            Alert.alert("오류", "삭제 실패");
          }
        },
      },
    ]);
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>키움증권 API 키 설정</Text>
        <Text style={styles.desc}>모의투자 환경이라면 mock=True 상태를 유지하세요.</Text>

        <Text style={styles.label}>App Key</Text>
        <TextInput
          style={styles.input}
          placeholder="발급받은 App Key 입력"
          value={appKey}
          onChangeText={setAppKey}
          autoCapitalize="none"
        />

        <Text style={styles.label}>Secret Key</Text>
        <TextInput
          style={styles.input}
          placeholder="발급받은 Secret Key 입력"
          value={secretKey}
          onChangeText={setSecretKey}
          secureTextEntry
          autoCapitalize="none"
        />

        <View style={styles.mockWrap}>
          <Text style={styles.label}>Mock 모드 (모의투자)</Text>
          <TouchableOpacity
            style={[styles.mockBtn, mock && styles.mockBtnActive]}
            onPress={() => setMock(!mock)}
          >
            <Text style={[styles.mockText, mock && styles.mockTextActive]}>
              {mock ? "활성화" : "비활성화"}
            </Text>
          </TouchableOpacity>
        </View>

        <TouchableOpacity
          style={[styles.btn, loading && { opacity: 0.6 }]}
          onPress={onSave}
          disabled={loading}
        >
          <Text style={styles.btnText}>저장</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.delBtn} onPress={onDelete}>
          <Text style={styles.delText}>API 키 삭제</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#fff" },
  container: { padding: 20 },
  title: { fontSize: 22, fontWeight: "800", marginBottom: 8 },
  desc: { color: "#6b7280", marginBottom: 20 },
  label: { fontWeight: "600", marginBottom: 6, marginTop: 14 },
  input: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 10,
    padding: 10,
    fontSize: 16,
  },
  mockWrap: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 14,
  },
  mockBtn: {
    borderWidth: 1,
    borderColor: "#9ca3af",
    borderRadius: 12,
    paddingVertical: 6,
    paddingHorizontal: 14,
  },
  mockBtnActive: { backgroundColor: "#111827", borderColor: "#111827" },
  mockText: { color: "#111827", fontWeight: "600" },
  mockTextActive: { color: "#fff" },

  btn: {
    backgroundColor: "#111827",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 24,
  },
  btnText: { color: "#fff", fontSize: 16, fontWeight: "700" },

  delBtn: { alignItems: "center", marginTop: 16 },
  delText: { color: "#dc2626", fontWeight: "600" },
});
