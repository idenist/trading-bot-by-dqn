import React, { useEffect, useState } from "react";
import { SafeAreaView, View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Alert } from "react-native";
import { startLink, getBrokerStatus, getAccounts, disconnect, setDefaultAccount, type BrokerStatus } from "@/lib/api/broker";

export default function AccountLinkScreen() {
  const [st, setSt] = useState<BrokerStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    try {
      setLoading(true);
      const s = await getBrokerStatus();
      setSt(s);
    } catch (e: any) {
      Alert.alert("상태 조회 실패", e?.response?.data?.detail ?? "네트워크 오류");
    } finally { setLoading(false); }
  };

  const onStart = async () => {
    try {
      setLoading(true);
      const s = await startLink();
      setSt(s);
    } catch (e: any) {
      Alert.alert("연결 시작 실패", e?.response?.data?.detail ?? "잠시 후 다시 시도해주세요.");
    } finally { setLoading(false); }
  };

  const onDisconnect = async () => {
    try {
      setLoading(true);
      const s = await disconnect();
      setSt(s);
    } catch (e: any) {
      Alert.alert("해제 실패", e?.response?.data?.detail ?? "잠시 후 다시 시도해주세요.");
    } finally { setLoading(false); }
  };

  const loadAccounts = async () => {
    try {
      setLoading(true);
      const s = await getAccounts();
      setSt(s);
    } catch (e: any) {
      Alert.alert("계좌 조회 실패", e?.response?.data?.detail ?? "잠시 후 다시 시도해주세요.");
    } finally { setLoading(false); }
  };

  useEffect(() => { refresh(); }, []);

  const statusColor = st?.status === "CONNECTED" ? "#16a34a"
                    : st?.status === "WAITING_LOGIN" ? "#2563eb"
                    : st?.status === "ERROR" ? "#dc2626" : "#6b7280";

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.card}>
        <Text style={s.title}>키움증권 계좌 연동</Text>
        <View style={s.row}>
          <Text style={s.muted}>상태</Text>
          <Text style={[s.badge, { backgroundColor: statusColor }]}>{st?.status ?? "DISCONNECTED"}</Text>
        </View>
        {!!st?.message && <Text style={[s.muted, { marginTop: 6 }]}>{st.message}</Text>}

        <View style={{ height: 12 }} />
        {loading ? <ActivityIndicator /> : (
          <>
            {st?.status === "CONNECTED" ? (
              <>
                <TouchableOpacity style={s.btn} onPress={loadAccounts}><Text style={s.btnTx}>계좌 목록 새로고침</Text></TouchableOpacity>
                <View style={{ height: 8 }} />
                {st?.accounts?.length ? (
                  <View style={s.accountsBox}>
                    {st.accounts.map(acc => (
                      <TouchableOpacity key={acc.accountNo} style={s.accRow}
                        onPress={async () => {
                          try { await setDefaultAccount(acc.accountNo); Alert.alert("완료", `${acc.accountNo}를 기본 계좌로 설정했습니다.`); }
                          catch { Alert.alert("오류", "계좌 설정에 실패했습니다."); }
                        }}>
                        <Text style={s.accNo}>{acc.accountNo}</Text>
                        <Text style={s.accName}>{acc.name ?? ""}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                ) : (
                  <Text style={s.muted}>연결됨 — “계좌 목록 새로고침”을 눌러 계좌를 불러오세요.</Text>
                )}
                <View style={{ height: 12 }} />
                <TouchableOpacity style={[s.btn, { backgroundColor: "#dc2626" }]} onPress={onDisconnect}>
                  <Text style={s.btnTx}>연결 해제</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <Text style={s.muted}>연결을 시작하면 데스크톱(키움 HTS)에서 로그인해 주세요.</Text>
                <View style={{ height: 12 }} />
                <TouchableOpacity style={s.btn} onPress={onStart}><Text style={s.btnTx}>연결 시작</Text></TouchableOpacity>
              </>
            )}
          </>
        )}

        <View style={{ height: 12 }} />
        <TouchableOpacity style={[s.btn, { backgroundColor: "#e5e7eb" }]} onPress={refresh}>
          <Text style={[s.btnTx, { color: "#111827" }]}>상태 새로고침</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#fff", padding: 16 },
  card: { borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 16, padding: 16 },
  title: { fontSize: 20, fontWeight: "800", marginBottom: 8 },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  muted: { color: "#6b7280" },
  badge: { color: "#fff", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, overflow: "hidden", fontWeight: "800" },
  btn: { backgroundColor: "#111827", borderRadius: 12, paddingVertical: 12, alignItems: "center" },
  btnTx: { color: "#fff", fontWeight: "800" },
  accountsBox: { marginTop: 8, borderWidth: 1, borderColor: "#e5e7eb", borderRadius: 12 },
  accRow: { padding: 12, borderBottomWidth: 1, borderBottomColor: "#e5e7eb" },
  accNo: { fontWeight: "800" }, accName: { color: "#6b7280" },
});
