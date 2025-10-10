// app/(tabs)/index.tsx
import { getPortfolio, getPositions } from "@/lib/api/portfolio";
import { PortfolioSnapshot, Position } from "@/lib/api/types";
import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  FlatList,
  RefreshControl,
  SafeAreaView,
  StyleSheet,
  Text,
  TouchableOpacity,
  useColorScheme,
  View,
} from "react-native";

/** ---------- 타입 (백엔드 붙일 때 그대로 교체) ---------- */
// type Currency = "KRW" | "USD";
// type PortfolioSnapshot = {
//   currency: Currency;
//   totalEquity: string;
//   cash: string;
//   pnlDay: string;   // "12345"
//   pnlDayPct: string; // "0.0123" -> 1.23%
//   updatedAt: string; // ISO
// };
// type Position = {
//   symbol: string;
//   name?: string;
//   qty: string;
//   avgPrice: string;
//   lastPrice: string;
//   pnl: string;
//   pnlPct: string; // "-0.0345"
// };

/** ---------- 더미 데이터 ---------- */
// const MOCK_PF: PortfolioSnapshot = {
//   currency: "KRW",
//   totalEquity: "123456789.12",
//   cash: "34567890",
//   pnlDay: "1234567",
//   pnlDayPct: "0.0082",
//   updatedAt: new Date().toISOString(),
// };

// const MOCK_POS: Position[] = [
//   { symbol: "005930.KS", name: "삼성전자", qty: "15", avgPrice: "78100", lastPrice: "79200", pnl: "16500", pnlPct: "0.0142" },
//   { symbol: "000660.KS", name: "SK하이닉스", qty: "3", avgPrice: "195000", lastPrice: "192500", pnl: "-7500", pnlPct: "-0.0128" },
// ];

/** ---------- 유틸 ---------- */
function Money({ v }: { v: string }) {
  let color;
  const txt = useMemo(() => {
    const n = Number(v);
    if (Number.isNaN(n)) return v;
    return n.toLocaleString();
  }, [v]);
  
  return <Text>{txt}</Text>;
}

function Pct({ v }: { v: string }) {
  const n = Number(v);
  const color = n > 0 ? "#16a34a" : n < 0 ? "#dc2626" : "#6b7280";
  const sign = n > 0 ? "+" : "";
  return <Text style={{ color, fontWeight: "700" }}>{sign}{(n * 100).toFixed(2)}%</Text>;
}

/** ---------- 컴포넌트 ---------- */
function SectionHeader({ title, onPressMore }: { title: string; onPressMore?: () => void }) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {onPressMore && (
        <TouchableOpacity onPress={onPressMore} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Text style={styles.more}>더보기</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

function EquityCard({ pf }: { pf: PortfolioSnapshot }) {
  return (
    <View style={styles.card}>
      <Text style={styles.muted}>총자산</Text>
      <Text style={styles.equity}><Money v={pf.totalEquity} /> {pf.currency}</Text>

      <View style={[styles.row, { marginTop: 6 }]}>
        <Text style={styles.muted}>총손익 </Text>
        <Text style={{ fontWeight: "700" }}>
          <Money v={pf.pnlDay} /> (<Pct v={pf.pnlDayPct} />)
        </Text>
      </View>

      <Text style={[styles.muted, { marginTop: 6 }]}>
        업데이트: {new Date(pf.updatedAt).toLocaleString()}
      </Text>
    </View>
  );
}

function QuickActions() {
  const Item = ({
    icon,
    label,
    onPress,
  }: {
    icon: React.ReactNode;
    label: string;
    onPress?: () => void;
  }) => (
    <TouchableOpacity style={styles.qaItem} onPress={onPress} activeOpacity={0.8}>
      <View style={styles.qaIcon}>{icon}</View>
      <Text style={styles.qaLabel}>{label}</Text>
    </TouchableOpacity>
  );

  return (
    <View style={styles.qaWrap}>
      <Item icon={<Feather name="search" size={20} />} label="종목검색" />
      <Item icon={<Feather name="plus-square" size={20} />} label="매수" />
      <Item icon={<Feather name="minus-square" size={20} />} label="매도" />
      <Item icon={<MaterialCommunityIcons name="robot-outline" size={20} />} label="봇 관리" />
    </View>
  );
}

function PositionRow({ item }: { item: Position }) {
  const color = Number(item.pnl) > 0 ? "#16a34a" : Number(item.pnl) < 0 ? "#dc2626" : "#6b7280";
  return (
    <View style={styles.posRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.symbol}>{item.symbol}{item.name ? ` · ${item.name}` : ""}</Text>
        <Text style={styles.sub}>{item.qty}주 @ <Money v={item.avgPrice} /></Text>
      </View>
      <View style={{ alignItems: "flex-end" }}>
        <Text style={styles.price}><Money v={item.lastPrice} /></Text>
        <Text style={{ color, fontWeight: "700" }}>
          <Money v={item.pnl} /> (<Pct v={item.pnlPct} />)
        </Text>
      </View>
    </View>
  );
}

/** ---------- 홈 화면 ---------- */
export default function Home() {
  const scheme = useColorScheme();
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);
  const [pf, setPf] = useState<PortfolioSnapshot | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);

  

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [portfolioData, positionsData] = await Promise.all([
        getPortfolio(),
        getPositions(),
      ]);
      setPf(portfolioData);
      setPositions(positionsData);
    } catch (error) {
      console.error("Failed to fetch data", error);
    } finally {
      setTimeout(() => setRefreshing(false), 700);
    }
  }, []);

  useEffect(() => {
    onRefresh();
  }, [onRefresh]);

  const bg = scheme === "dark" ? "#0b0f14" : "#fff";

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: bg }]}>
      <FlatList
        ListHeaderComponent={
          <>
            {pf ? <EquityCard pf={pf} /> : null}
            <QuickActions />
            <SectionHeader title="보유 종목" onPressMore={() => {}} />
          </>
        }
        data={positions}
        keyExtractor={(it) => it.symbol}
        renderItem={({ item }) => (
          <TouchableOpacity
            activeOpacity={0.8}
            onPress={() => router.push({ pathname: "/trade/[symbol]", params: { symbol: item.symbol, name: item.name ?? "" } })}
          >
            <PositionRow item={item} />
          </TouchableOpacity>
        )}
        ItemSeparatorComponent={() => <View style={{ height: 10 }} />}
        contentContainerStyle={{ padding: 16, paddingBottom: 24 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.muted}>보유 종목이 없습니다</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

/** ---------- 스타일 ---------- */
const styles = StyleSheet.create({
  safe: { flex: 1 },
  muted: { color: "#6b7280" },

  card: {
    backgroundColor: "#f8fafc",
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  equity: { fontSize: 28, fontWeight: "800", marginTop: 4 },

  row: { flexDirection: "row", alignItems: "center" },

  sectionHeader: {
    marginTop: 8,
    marginBottom: 10,
    paddingHorizontal: 2,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: { fontSize: 16, fontWeight: "700" },
  more: { color: "#2563eb", fontWeight: "600" },

  qaWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    marginBottom: 12,
  },
  qaItem: {
    width: "23.5%",
    alignItems: "center",
    gap: 6,
  },
  qaIcon: {
    width: 56,
    height: 56,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#fff",
  },
  qaLabel: { fontSize: 12, color: "#111" },

  posRow: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    flexDirection: "row",
    alignItems: "center",
  },
  symbol: { fontSize: 16, fontWeight: "700" },
  sub: { color: "#6b7280", marginTop: 2 },
  price: { fontSize: 16, fontWeight: "700" },

  empty: { paddingVertical: 28, alignItems: "center" },
});
