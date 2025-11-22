// frontend/app/(tabs)/trade/[symbol].tsx
import { Feather } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { getChartData } from "@/lib/api/chart";
import Chart from "@/components/Chart";
import type { ChartDatum } from "@/lib/api/types";
import { getStockInfo } from "@/lib/api/stocks";

import { placeOrderApi, startAutoTrade } from "@/lib/api/trade";

const MAX_CANDLES = 40;

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

  const [crt, setChart] = useState<ChartDatum[]>([]);
  const [chartLoading, setChartLoading] = useState(true);

  const [quote, setQuote] = useState<Quote | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(true);

  // 종목 현재가/등락률 로드
  useEffect(() => {
    if (!symbol) return;
    setQuoteLoading(true);
    (async () => {
      try {
        const info = await getStockInfo(symbol);
        setQuote({
          symbol: info.symbol,
          name: name || info.name,
          price: info.price,
          changePct: info.changePct,
        });
      } catch (e) {
        console.error("getStockInfo failed:", e);
        Alert.alert("오류", "종목 정보를 불러오지 못했습니다.");
      } finally {
        setQuoteLoading(false);
      }
    })();
  }, [symbol, name]);

  // 차트 데이터 로드
  useEffect(() => {
    if (!symbol) return;
    setChartLoading(true);
    getChartData((symbol as string) ?? "005930", "1D", 20)
      .then(setChart)
      .catch((e) => {
        console.error("chart load error", e);
        setChart([]); // 에러 시 빈 배열
      })
      .finally(() => setChartLoading(false));
  }, [symbol]);

  const isLoading = quoteLoading || !quote;

  const displayed = React.useMemo(
    () => (crt.length > MAX_CANDLES ? crt.slice(-MAX_CANDLES) : crt),
    [crt],
  );

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView contentContainerStyle={{ padding: 16 }}>
          {isLoading ? (
            <View style={{ alignItems: "center", justifyContent: "center", paddingVertical: 40 }}>
              <Text>종목 정보를 불러오는 중입니다…</Text>
            </View>
          ) : (
            <>
              <Header quote={quote!} onBack={() => router.back()} />

              {/* 차트 카드 */}
              <View style={styles.chartCard}>
                <View style={styles.chartArea}>
                  <Chart data={displayed} />
                </View>
              </View>

              
              <OrderPanel
                symbol={quote!.symbol}
                lastPrice={quote!.price}
              />

            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

/** ---------- 상단 헤더(현재가/등락) ---------- */
function Header({ quote, onBack }: { quote: Quote; onBack: () => void }) {
  return (
    <View style={styles.header}>
      <TouchableOpacity
        onPress={onBack}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
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

function showAlert(title: string, message: string) {
  if (Platform.OS === "web") {
    // 웹에서는 브라우저 alert 사용
    window.alert(`${title}\n\n${message}`);
  } else {
    Alert.alert(title, message);
  }
}

/** ---------- 주문 패널 ---------- */
function OrderPanel({
  symbol,
  lastPrice,
}: {
  symbol: string;
  lastPrice: number;
}) {
  const [side, setSide] = useState<OrderSide>("BUY");
  const [type, setType] = useState<OrderType>("LIMIT");
  const [price, setPrice] = useState(String(lastPrice));
  const [qty, setQty] = useState("1");
  const [submitting, setSubmitting] = useState(false);

  // lastPrice 로드 후 기본값 맞추기
  useEffect(() => {
    setPrice(String(lastPrice));
  }, [lastPrice]);

  // 예상 주문금액 (자동매매 예산으로도 사용)
  const notional = useMemo(
    () =>
      (type === "MARKET" ? lastPrice : Number(price || 0)) *
      Number(qty || 0),
    [type, price, qty, lastPrice],
  );

  const canSubmit =
    Number(qty) > 0 && (type === "MARKET" || Number(price) > 0);

  const onTick = (dir: 1 | -1) => {
    const p = Number(price || 0);
    const next = Math.max(0, p + dir * 100); // 실제 최소호가는 나중에 조정
    setPrice(String(next));
  };

  // ===== 수동 주문 =====
  const submit = async () => {
    if (!canSubmit || submitting) return;

    const body = {
      symbol,
      side,
      type,
      price: type === "MARKET" ? 0 : Number(price),
      qty: Number(qty),
    };

    const summary =
      `${symbol}\n` +
      `${side === "BUY" ? "매수" : "매도"} / ${
        type === "MARKET" ? "시장가" : "지정가"
      }\n` +
      `가격: ${
        type === "MARKET" ? "시장가" : formatNum(Number(price))
      }\n` +
      `수량: ${qty}\n` +
      `주문금액: ${formatNum(notional)} KRW`;

    const doRequest = async () => {
      try {
        setSubmitting(true);
        const res = await placeOrderApi(body);
        const title = res.success ? "주문 접수" : "주문 실패";
        const detail = res.message ?? "";

        const msg = res.success
          ? `${title}\n\norderId: ${res.orderId}`
          : `${title}\n\n⚠ ${detail} (orderId: ${res.orderId})`;

        if (Platform.OS === "web") {
          window.alert(msg);
        } else {
          Alert.alert(title, msg);
        }
      } catch (e: any) {
        console.error("order error", e);
        const msg = e?.response?.data?.detail ?? String(e);
        if (Platform.OS === "web") {
          window.alert(`주문 실패: ${msg}`);
        } else {
          Alert.alert("주문 실패", msg);
        }
      } finally {
        setSubmitting(false);
      }
    };

    if (Platform.OS === "web") {
      if (window.confirm(`주문 확인\n\n${summary}`)) {
        await doRequest();
      }
    } else {
      Alert.alert("주문 확인", summary, [
        { text: "취소", style: "cancel" },
        { text: "주문", onPress: () => void doRequest() },
      ]);
    }
  };

  // ===== 자동 매매: 현재 입력된 notional을 예산으로 사용 =====
  const handleAutoTrade = async () => {
    const budget = Math.floor(notional);

    if (!Number.isFinite(budget) || budget <= 0) {
      const msg = "자동 매매 전에 가격과 수량을 먼저 입력해주세요.";
      if (Platform.OS === "web") {
        window.alert(msg);
      } else {
        Alert.alert("입력 오류", msg);
      }
      return;
    }

    const summary =
      `${symbol} 자동 매매를 시작합니다.\n\n` +
      `예산: ${formatNum(budget)} KRW\n` +
      "(현재 입력된 가격 × 수량 기준)\n\n" +
      "변경하려면 취소 후 가격/수량을 다시 설정하세요.";

    const run = async () => {
      try {
        setSubmitting(true);

        // ⬇ 기존 startAutoTrade 시그니처 유지: (stocks: string[], amountPerStock: number)
        const res = await startAutoTrade([symbol], budget);

        if (!res.success) {
          const detail = res.message ?? "알 수 없는 오류";
          if (Platform.OS === "web") {
            window.alert(`자동 매매 시작 실패: ${detail}`);
          } else {
            Alert.alert("자동 매매 시작 실패", detail);
          }
          return;
        }

        const okMsg =
          `${symbol} 자동 매매가 시작되었습니다.\n\n` +
          `예산: ${formatNum(budget)} KRW`;

        if (Platform.OS === "web") {
          window.alert(okMsg);
        } else {
          Alert.alert("자동 매매 시작", okMsg);
        }
      } catch (e: any) {
        console.error("[AUTO] start error", e);
        const detail = e?.response?.data?.detail ?? String(e);
        if (Platform.OS === "web") {
          window.alert(`자동 매매 시작 실패: ${detail}`);
        } else {
          Alert.alert("자동 매매 시작 실패", detail);
        }
      } finally {
        setSubmitting(false);
      }
    };

    if (Platform.OS === "web") {
      if (window.confirm(summary)) {
        await run();
      }
    } else {
      Alert.alert("자동 매매", summary, [
        { text: "취소", style: "cancel" },
        { text: "시작", onPress: () => void run() },
      ]);
    }
  };

  return (
    <View style={styles.orderCard}>
      {/* 사이드 탭 */}
      <View style={styles.sideTabs}>
        <TouchableOpacity
          style={[styles.sideTab, side === "BUY" && styles.sideTabActiveBuy]}
          onPress={() => setSide("BUY")}
        >
          <Text
            style={[
              styles.sideTabText,
              side === "BUY" && styles.sideTabTextActive,
            ]}
          >
            매수
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.sideTab, side === "SELL" && styles.sideTabActiveSell]}
          onPress={() => setSide("SELL")}
        >
          <Text
            style={[
              styles.sideTabText,
              side === "SELL" && styles.sideTabTextActive,
            ]}
          >
            매도
          </Text>
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
              <Text style={styles.marketPrice}>
                {formatNum(lastPrice)} (시장가)
              </Text>
            </View>
          ) : (
            <View style={styles.priceRow}>
              <TouchableOpacity
                style={styles.stepBtn}
                onPress={() => onTick(-1)}
              >
                <Feather name="minus" size={16} />
              </TouchableOpacity>
              <TextInput
                keyboardType="numeric"
                value={price}
                onChangeText={setPrice}
                style={styles.input}
                placeholder="가격"
              />
              <TouchableOpacity
                style={styles.stepBtn}
                onPress={() => onTick(1)}
              >
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
            {["1", "5", "10", "20"].map((q) => (
              <TouchableOpacity
                key={q}
                style={styles.qtyPill}
                onPress={() => setQty(q)}
              >
                <Text style={styles.qtyPillText}>{q}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </Field>

        {/* 요약 */}
        <View style={styles.summary}>
          <Text style={styles.summaryKey}>예상 주문금액</Text>
          <Text style={styles.summaryVal}>
            {formatNum(
              Number(Number.isFinite(notional) ? notional : 0),
            )}{" "}
            KRW
          </Text>
        </View>

        {/* 수동 주문 버튼 */}
        <TouchableOpacity
          style={[
            styles.submitBtn,
            !canSubmit && { opacity: 0.5 },
            side === "BUY" ? styles.buyBtn : styles.sellBtn,
          ]}
          onPress={submit}
          disabled={!canSubmit || submitting}
          activeOpacity={0.8}
        >
          <Text style={styles.submitText}>
            {side === "BUY" ? "매수 주문" : "매도 주문"}
          </Text>
        </TouchableOpacity>

        {/* 자동 매매 버튼 */}
        <TouchableOpacity
          style={styles.autoBtn}
          onPress={handleAutoTrade}
          disabled={submitting}
          activeOpacity={0.85}
        >
          <Text style={styles.autoBtnText}>자동 매매</Text>
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
            <Text
              style={[
                styles.toggleText,
                active && styles.toggleTextActive,
              ]}
            >
              {opt.label}
            </Text>
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
  chartArea: {
    height: 200,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    overflow: "hidden",
  },

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

  autoBtn: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 10,
    backgroundColor: "#0ea5e9",
  },
  autoBtnText: { color: "#fff", fontWeight: "800", fontSize: 16 },
});
