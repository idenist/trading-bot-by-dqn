// app/trade/[symbol].tsx
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
import Chart from "../../components/Chart";
import type { ChartDatum } from "../../lib/api/types";

const rawData = [
  {'timestamp': 1703689200, 'open': 77700.0, 'high': 78500.0, 'low': 77500.0, 'close': 78500.0},
  {'timestamp': 1703602800, 'open': 76700.0, 'high': 78000.0, 'low': 76500.0, 'close': 78000.0},
  {'timestamp': 1703516400, 'open': 76100.0, 'high': 76700.0, 'low': 75700.0, 'close': 76600.0},
  {'timestamp': 1703170800, 'open': 75800.0, 'high': 76300.0, 'low': 75400.0, 'close': 75900.0},
  {'timestamp': 1703084400, 'open': 74600.0, 'high': 75000.0, 'low': 74300.0, 'close': 75000.0},
  {'timestamp': 1702998000, 'open': 74200.0, 'high': 74900.0, 'low': 73800.0, 'close': 74800.0},
  {'timestamp': 1702911600, 'open': 73000.0, 'high': 73400.0, 'low': 72800.0, 'close': 73400.0},
  {'timestamp': 1702825200, 'open': 73300.0, 'high': 73400.0, 'low': 72800.0, 'close': 72900.0},
  {'timestamp': 1702566000, 'open': 73800.0, 'high': 74000.0, 'low': 73200.0, 'close': 73300.0},
  {'timestamp': 1702479600, 'open': 74100.0, 'high': 74300.0, 'low': 72500.0, 'close': 73100.0},
  {'timestamp': 1702393200, 'open': 73300.0, 'high': 73500.0, 'low': 72800.0, 'close': 72800.0},
  {'timestamp': 1702306800, 'open': 73300.0, 'high': 73500.0, 'low': 73100.0, 'close': 73500.0},
  {'timestamp': 1702220400, 'open': 72800.0, 'high': 73000.0, 'low': 72200.0, 'close': 73000.0},
  {'timestamp': 1701961200, 'open': 72100.0, 'high': 72800.0, 'low': 71900.0, 'close': 72600.0},
  {'timestamp': 1701874800, 'open': 71800.0, 'high': 71900.0, 'low': 71100.0, 'close': 71500.0},
  {'timestamp': 1701788400, 'open': 71800.0, 'high': 72100.0, 'low': 71600.0, 'close': 71700.0},
  {'timestamp': 1701702000, 'open': 72300.0, 'high': 72400.0, 'low': 71200.0, 'close': 71200.0},
  {'timestamp': 1701615600, 'open': 72800.0, 'high': 72900.0, 'low': 72400.0, 'close': 72600.0},
  {'timestamp': 1701356400, 'open': 72400.0, 'high': 72500.0, 'low': 71700.0, 'close': 72000.0},
  {'timestamp': 1701270000, 'open': 72700.0, 'high': 72800.0, 'low': 72200.0, 'close': 72800.0},
  {'timestamp': 1701183600, 'open': 72400.0, 'high': 72800.0, 'low': 72200.0, 'close': 72700.0},
  {'timestamp': 1701097200, 'open': 71400.0, 'high': 72700.0, 'low': 71300.0, 'close': 72700.0},
  {'timestamp': 1701010800, 'open': 71500.0, 'high': 72100.0, 'low': 71100.0, 'close': 71300.0},
  {'timestamp': 1700751600, 'open': 72400.0, 'high': 72600.0, 'low': 71700.0, 'close': 71700.0},
  {'timestamp': 1700665200, 'open': 73000.0, 'high': 73200.0, 'low': 72200.0, 'close': 72400.0},
  {'timestamp': 1700578800, 'open': 72200.0, 'high': 73000.0, 'low': 71900.0, 'close': 72800.0},
  {'timestamp': 1700492400, 'open': 73100.0, 'high': 73400.0, 'low': 72700.0, 'close': 72800.0},
  {'timestamp': 1700406000, 'open': 72100.0, 'high': 73000.0, 'low': 72100.0, 'close': 72700.0},
  {'timestamp': 1700146800, 'open': 72300.0, 'high': 73000.0, 'low': 72300.0, 'close': 72500.0},
  {'timestamp': 1700060400, 'open': 72500.0, 'high': 73000.0, 'low': 72300.0, 'close': 72800.0},
  {'timestamp': 1699974000, 'open': 71600.0, 'high': 72200.0, 'low': 71500.0, 'close': 72200.0},
  {'timestamp': 1699887600, 'open': 71000.0, 'high': 71100.0, 'low': 70600.0, 'close': 70800.0},
];
const data: ChartDatum[] = rawData.map(d => ({
  timestamp: d.timestamp * 1000,
  open: d.open,
  high: d.high,
  low: d.low,
  close: d.close,
})); // ms 변환

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
// const chartData = [{'timestamp': 1703689200, 'open': 77700.0, 'high': 78500.0, 'low': 77500.0, 'close': 78500.0}, {'timestamp': 1703602800, 'open': 76700.0, 'high': 78000.0, 'low': 76500.0, 'close': 78000.0}, {'timestamp': 1703516400, 'open': 76100.0, 'high': 76700.0, 'low': 75700.0, 'close': 76600.0}, {'timestamp': 1703170800, 'open': 75800.0, 'high': 76300.0, 'low': 75400.0, 'close': 75900.0}, {'timestamp': 1703084400, 'open': 74600.0, 'high': 75000.0, 'low': 74300.0, 'close': 75000.0}, {'timestamp': 1702998000, 'open': 74200.0, 'high': 74900.0, 'low': 73800.0, 'close': 74800.0}, {'timestamp': 1702911600, 'open': 73000.0, 'high': 73400.0, 'low': 72800.0, 'close': 73400.0}, {'timestamp': 1702825200, 'open': 73300.0, 'high': 73400.0, 'low': 72800.0, 'close': 72900.0}, {'timestamp': 1702566000, 'open': 73800.0, 'high': 74000.0, 'low': 73200.0, 'close': 73300.0}, {'timestamp': 1702479600, 'open': 74100.0, 'high': 74300.0, 'low': 72500.0, 'close': 73100.0}, {'timestamp': 1702393200, 'open': 73300.0, 'high': 73500.0, 'low': 72800.0, 'close': 72800.0}, {'timestamp': 1702306800, 'open': 73300.0, 'high': 73500.0, 'low': 73100.0, 'close': 73500.0}, {'timestamp': 1702220400, 'open': 72800.0, 'high': 73000.0, 'low': 72200.0, 'close': 73000.0}, {'timestamp': 1701961200, 'open': 72100.0, 'high': 72800.0, 'low': 71900.0, 'close': 72600.0}, {'timestamp': 1701874800, 'open': 71800.0, 'high': 71900.0, 'low': 71100.0, 'close': 71500.0}, {'timestamp': 1701788400, 'open': 71800.0, 'high': 72100.0, 'low': 71600.0, 'close': 71700.0}, {'timestamp': 1701702000, 'open': 72300.0, 'high': 72400.0, 'low': 71200.0, 'close': 71200.0}, {'timestamp': 1701615600, 'open': 72800.0, 'high': 72900.0, 'low': 72400.0, 'close': 72600.0}, {'timestamp': 1701356400, 'open': 72400.0, 'high': 72500.0, 'low': 71700.0, 'close': 72000.0}, {'timestamp': 1701270000, 'open': 72700.0, 'high': 72800.0, 'low': 72200.0, 'close': 72800.0}, {'timestamp': 1701183600, 'open': 72400.0, 'high': 72800.0, 'low': 72200.0, 'close': 72800.0}, {'timestamp': 1701097200, 'open': 72000.0, 'high': 72300.0, 'low': 71700.0, 'close': 72200.0}, {'timestamp': 1701010800, 'open': 71300.0, 'high': 71500.0, 'low': 71000.0, 'close': 71300.0}, {'timestamp': 1700751600, 'open': 71000.0, 'high': 71200.0, 'low': 70700.0, 'close': 71200.0}, {'timestamp': 1700665200, 'open': 70500.0, 'high': 70800.0, 'low': 70300.0, 'close': 70700.0}, {'timestamp': 1700578800, 'open': 70600.0, 'high': 70800.0, 'low': 70400.0, 'close': 70500.0}, {'timestamp': 1700492400, 'open': 72500.0, 'high': 72800.0, 'low': 72300.0, 'close': 72700.0}, {'timestamp': 1700406000, 'open': 72800.0, 'high': 73000.0, 'low': 72500.0, 'close': 72800.0}, {'timestamp': 1700146800, 'open': 72300.0, 'high': 72500.0, 'low': 72100.0, 'close': 72200.0}, {'timestamp': 1700060400, 'open': 72200.0, 'high': 72400.0, 'low': 72000.0, 'close': 72200.0}, {'timestamp': 1699974000, 'open': 72200.0, 'high': 72300.0, 'low': 71500.0, 'close': 72000.0}, {'timestamp': 1699887600, 'open': 70800.0, 'high': 71000.0, 'low': 70600.0, 'close': 70900.0}, {'timestamp': 1699801200, 'open': 70800.0, 'high': 71000.0, 'low': 70500.0, 'close': 70600.0}, {'timestamp': 1699542000, 'open': 70300.0, 'high': 70500.0, 'low': 69800.0, 'close': 70100.0}, {'timestamp': 1699455600, 'open': 69600.0, 'high': 70000.0, 'low': 69500.0, 'close': 69700.0}, {'timestamp': 1699369200, 'open': 70900.0, 'high': 71000.0, 'low': 70500.0, 'close': 70600.0}, {'timestamp': 1699282800, 'open': 70200.0, 'high': 70500.0, 'low': 69800.0, 'close': 70500.0}, {'timestamp': 1699196400, 'open': 69700.0, 'high': 69800.0, 'low': 69300.0, 'close': 69500.0}, {'timestamp': 1698937200, 'open': 68600.0, 'high': 69600.0, 'low': 68500.0, 'close': 69600.0}, {'timestamp': 1698850800, 'open': 68000.0, 'high': 68400.0, 'low': 67800.0, 'close': 68300.0}, {'timestamp': 1698764400, 'open': 67300.0, 'high': 67900.0, 'low': 67300.0, 'close': 67800.0}, {'timestamp': 1698678000, 'open': 67600.0, 'high': 67800.0, 'low': 67300.0, 'close': 67300.0}, {'timestamp': 1698332400, 'open': 67000.0, 'high': 67500.0, 'low': 66800.0, 'close': 67500.0}, {'timestamp': 1698246000, 'open': 67000.0, 'high': 67300.0, 'low': 66700.0, 'close': 67000.0}, {'timestamp': 1698159600, 'open': 68000.0, 'high': 68300.0, 'low': 67800.0, 'close': 68000.0}, {'timestamp': 1698073200, 'open': 68900.0, 'high': 69000.0, 'low': 68300.0, 'close': 68300.0}, {'timestamp': 1697727600, 'open': 69500.0, 'high': 69600.0, 'low': 68800.0, 'close': 69000.0}, {'timestamp': 1697641200, 'open': 70000.0, 'high': 70000.0, 'low': 69200.0, 'close': 69200.0}, {'timestamp': 1697554800, 'open': 69300.0, 'high': 69800.0, 'low': 69100.0, 'close': 69800.0}];
export default function SymbolDetailScreen() {
  const { symbol, name } = useLocalSearchParams<{ symbol: string; name?: string }>();
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);
  const [crt, setChart] = useState<ChartDatum[]>([]);
  const [loading, setLoading] = useState(true);

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

  useEffect(() => {
    setLoading(true);
    getChartData(symbol ?? "005963", "1D", "2025-01-01", 30)
      .then(setChart)
      .finally(() => setLoading(false));
  }, [symbol]);
  
  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16 }}>
          <Header quote={quote} onBack={() => router.back()} />

          <Chart data={crt} />

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

/** ---------- 주문 패널 ---------- */

function OrderPanel({
  symbol,
  lastPrice,
  onAutoTrade,
}: {
  symbol: string;
  lastPrice: number;
  onAutoTrade?: (symbol: string) => void;
}) {
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

        <TouchableOpacity
          style={styles.autoBtn}
          onPress={() =>
            onAutoTrade ? onAutoTrade(symbol) : Alert.alert("자동 매매", "봇 관리 화면으로 연결하세요.")
          }
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
  autoBtn: {
  borderRadius: 12,
  paddingVertical: 14,
  alignItems: "center",
  marginTop: 10,                 // 제출 버튼과 간격
  backgroundColor: "#0ea5e9",    // 파란 계열(원하면 바꾸세요)
},
autoBtnText: { color: "#fff", fontWeight: "800", fontSize: 16 },

});
