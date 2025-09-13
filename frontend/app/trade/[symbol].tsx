// app/trade/[symbol].tsx
import React, { useEffect, useMemo, useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  Alert,
  ScrollView,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";

/** ---------- 타입 ---------- */
type OrderSide = "BUY" | "SELL";
type OrderType = "MARKET" | "LIMIT";

type Quote = {
  symbol: string;
  name?: string;
  price: number;
  changePct: number; // 0.0123 = +1.23%
};

function formatNum(n: number) {
  return n.toLocaleString();
}
function signColor(x: number) {
  return x > 0 ? "#16a34a" : x < 0 ? "#dc2626" : "#6b7280";
}

/** ---------- 메인 ---------- */
export default function SymbolDetailScreen() {
  const { symbol, name } = useLocalSearchParams<{ symbol: string; name?: string }>();
  const router = useRouter();

  // 임시: 틱커 모킹
  const [quote, setQuote] = useState<Quote>({
    symbol: symbol ?? "000000.KS",
    name,
    price: 79200,
    changePct: 0.0142,
  });

  useEffect(() => {
    // 더미 실시간: 1초마다 ±변동
    const id = setInterval(() => {
      setQuote((q) => {
        const delta = (Math.random() - 0.5) * 200; // ±200원
        const next = Math.max(1, q.price + delta);
        // 변동률은 대충 계산(실서비스는 전일종가로 계산)
        const cp = (next - 78000) / 78000;
        return { ...q, price: Math.round(next), changePct: cp };
      });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16 }}>
          <Header quote={quote} onBack={() => router.back()} />

          <ChartPlaceholder />

          <OrderPanel symbol={quote.symbol} lastPrice={quote.price} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

/** ---------- 상단 헤더(현재가/등락) ---------- */
function Header({ quote, onBack }: { quote: Quote; onBack: () => void }) {
  return (
    <View style={styles.header}>
      <TouchableOpacity onPress={onBack} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
        <Feather name="chevron-left" size={24} />
      </TouchableOpacity>
      <View style={{ marginLeft: 8, flex: 1 }}>
        <Text style={styles.symbol}>
          {quote.symbol}
          {quote.name ? ` · ${quote.name}` : ""}
        </Text>
        <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 8 }}>
          <Text style={styles.price}>{formatNum(quote.price)}</Text>
          <Text style={[styles.pct, { color: signColor(quote.changePct) }]}>
            {(quote.changePct * 100).toFixed(2)}%
          </Text>
        </View>
      </View>
      <View style={{ width: 24 }} />
    </View>
  );
}

/** ---------- 차트 플레이스홀더 ---------- */
function ChartPlaceholder() {
  return (
    <View style={styles.chartCard}>
      <View style={styles.chartTabs}>
        {["1D", "1W", "1M", "3M", "1Y"].map((t, i) => (
          <TouchableOpacity key={t} style={[styles.tab, i === 0 && styles.tabActive]}>
            <Text style={[styles.tabText, i === 0 && styles.tabTextActive]}>{t}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.chartArea}>
        <Text style={{ color: "#94a3b8" }}>여기에 캔들 차트를 붙이세요 (victory-native / skia)</Text>
      </View>
      <View style={styles.statRow}>
        <Text style={styles.statKey}>고가</Text><Text style={styles.statVal}>80,100</Text>
        <Text style={styles.statKey}>저가</Text><Text style={styles.statVal}>77,800</Text>
        <Text style={styles.statKey}>거래량</Text><Text style={styles.statVal}>2,345,678</Text>
      </View>
    </View>
  );
}

/** ---------- 주문 패널 ---------- */
function OrderPanel({ symbol, lastPrice }: { symbol: string; lastPrice: number }) {
  const [side, setSide] = useState<OrderSide>("BUY");
  const [type, setType] = useState<OrderType>("LIMIT");
  const [price, setPrice] = useState(String(lastPrice));
  const [qty, setQty] = useState("1");

  // 간단 계산(수수료/슬리피지는 나중에 실제 값 반영)
  const notional = useMemo(() => (type === "MARKET" ? lastPrice : Number(price || 0)) * Number(qty || 0), [type, price, qty, lastPrice]);

  const canSubmit =
    Number(qty) > 0 &&
    (type === "MARKET" || Number(price) > 0);

  const onTick = (dir: 1 | -1) => {
    const p = Number(price || 0);
    const next = Math.max(0, p + dir * 100); // 코스피 최소호가 대략 50/100원 단위, 임시 100원
    setPrice(String(next));
  };

  const submit = () => {
    if (!canSubmit) return;
    // 여기에 실제 주문 API 호출(멱등키 포함)
    Alert.alert(
      "주문 확인",
      `${symbol}\n${side === "BUY" ? "매수" : "매도"} / ${type}\n가격: ${type === "MARKET" ? "시장가" : formatNum(Number(price))}\n수량: ${qty}\n주문금액: ${formatNum(notional)}`,
    );
  };

  return (
    <View style={styles.orderCard}>
      {/* 사이드 탭 */}
      <View style={styles.sideTabs}>
        <TouchableOpacity
          style={[styles.sideTab, side === "BUY" && styles.sideTabActiveBuy]}
          onPress={() => setSide("BUY")}
        >
          <Text style={[styles.sideTabText, side === "BUY" && styles.sideTabTextActive]}>매수</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.sideTab, side === "SELL" && styles.sideTabActiveSell]}
          onPress={() => setSide("SELL")}
        >
          <Text style={[styles.sideTabText, side === "SELL" && styles.sideTabTextActive]}>매도</Text>
        </TouchableOpacity>
      </View>

      {/* 주문유형 */}
      <View style={styles.typeRow}>
        <Toggle
          options={[
            { key: "LIMIT", label: "지정가" },
            { key: "MARKET", label: "시장가" },
          ]}
          value={type}
          onChange={(v) => setType(v as OrderType)}
        />
      </View>

      {/* 가격/수량 */}
      <View style={{ gap: 10 }}>
        <Field label="가격">
          {type === "MARKET" ? (
            <View style={styles.inline}>
              <Text style={styles.marketPrice}>{formatNum(lastPrice)} (시장가)</Text>
            </View>
          ) : (
            <View style={styles.priceRow}>
              <TouchableOpacity style={styles.stepBtn} onPress={() => onTick(-1)}>
                <Feather name="minus" size={16} />
              </TouchableOpacity>
              <TextInput
                keyboardType="numeric"
                value={price}
                onChangeText={setPrice}
                style={styles.input}
                placeholder="가격"
              />
              <TouchableOpacity style={styles.stepBtn} onPress={() => onTick(1)}>
                <Feather name="plus" size={16} />
              </TouchableOpacity>
            </View>
          )}
        </Field>

        <Field label="수량">
          <TextInput
            keyboardType="numeric"
            value={qty}
            onChangeText={setQty}
            style={styles.input}
            placeholder="수량"
          />
          <View style={styles.qtyQuick}>
            {["1","5","10","20"].map((q)=>(
              <TouchableOpacity key={q} style={styles.qtyPill} onPress={()=>setQty(q)}>
                <Text style={styles.qtyPillText}>{q}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </Field>

        {/* 요약 */}
        <View style={styles.summary}>
          <Text style={styles.summaryKey}>예상 주문금액</Text>
          <Text style={styles.summaryVal}>{formatNum(Number(isFinite(notional) ? notional : 0))} KRW</Text>
        </View>

        <TouchableOpacity
          style={[styles.submitBtn, !canSubmit && { opacity: 0.5 } , side === "BUY" ? styles.buyBtn : styles.sellBtn]}
          onPress={submit}
          disabled={!canSubmit}
          activeOpacity={0.8}
        >
          <Text style={styles.submitText}>{side === "BUY" ? "매수 주문" : "매도 주문"}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

/** ---------- 보조 컴포넌트 ---------- */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={{ marginBottom: 8 }}>
      <Text style={styles.fieldLabel}>{label}</Text>
      {children}
    </View>
  );
}

function Toggle<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { key: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <View style={styles.toggleWrap}>
      {options.map((opt) => {
        const active = opt.key === value;
        return (
          <TouchableOpacity
            key={opt.key}
            style={[styles.toggleBtn, active && styles.toggleBtnActive]}
            onPress={() => onChange(opt.key)}
          >
            <Text style={[styles.toggleText, active && styles.toggleTextActive]}>{opt.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

/** ---------- 스타일 ---------- */
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#fff" },

  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 12,
  },
  symbol: { fontSize: 16, fontWeight: "700" },
  price: { fontSize: 24, fontWeight: "800", marginTop: 2 },
  pct: { fontSize: 14, fontWeight: "700" },

  chartCard: {
    backgroundColor: "#f8fafc",
    borderRadius: 16,
    padding: 12,
    marginBottom: 16,
  },
  chartTabs: { flexDirection: "row", gap: 8, marginBottom: 8 },
  tab: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 10,
    backgroundColor: "#e2e8f0",
  },
  tabActive: { backgroundColor: "#1f2937" },
  tabText: { color: "#0f172a", fontWeight: "600" },
  tabTextActive: { color: "#fff" },
  chartArea: {
    height: 200,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  statRow: {
    marginTop: 10,
    flexDirection: "row",
    gap: 12,
    flexWrap: "wrap",
  },
  statKey: { color: "#64748b" },
  statVal: { fontWeight: "700" },

  orderCard: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    marginBottom: 24,
  },

  sideTabs: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 10,
  },
  sideTab: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    backgroundColor: "#fff",
  },
  sideTabActiveBuy: { backgroundColor: "#ecfdf5", borderColor: "#16a34a" },
  sideTabActiveSell: { backgroundColor: "#fef2f2", borderColor: "#dc2626" },
  sideTabText: { fontWeight: "700", color: "#111827" },
  sideTabTextActive: { color: "#111827" },

  typeRow: { marginBottom: 8 },
  toggleWrap: {
    flexDirection: "row",
    backgroundColor: "#f1f5f9",
    borderRadius: 12,
    padding: 4,
    gap: 4,
  },
  toggleBtn: {
    flex: 1,
    paddingVertical: 8,
    alignItems: "center",
    borderRadius: 8,
  },
  toggleBtnActive: { backgroundColor: "#fff" },
  toggleText: { color: "#334155", fontWeight: "600" },
  toggleTextActive: { color: "#111827", fontWeight: "800" },

  fieldLabel: { color: "#6b7280", marginBottom: 6 },
  input: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
  },
  priceRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  stepBtn: {
    width: 40,
    height: 40,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#fff",
  },
  inline: { flexDirection: "row", alignItems: "center", gap: 8 },
  marketPrice: { fontWeight: "700" },

  qtyQuick: { flexDirection: "row", gap: 8, marginTop: 8 },
  qtyPill: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    backgroundColor: "#fff",
  },
  qtyPillText: { fontWeight: "600" },

  summary: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 8,
    marginBottom: 12,
  },
  summaryKey: { color: "#64748b" },
  summaryVal: { fontWeight: "800" },

  submitBtn: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  buyBtn: { backgroundColor: "#16a34a" },
  sellBtn: { backgroundColor: "#dc2626" },
  submitText: { color: "#fff", fontWeight: "800", fontSize: 16 },
});
