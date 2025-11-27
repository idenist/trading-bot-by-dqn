import { getPortfolio, getPositions } from "@/lib/api/portfolio";
import { PortfolioSnapshot, Position } from "@/lib/api/types";
import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { useRouter, useFocusEffect, useLocalSearchParams } from "expo-router";
import { getApiKeys, logoutApi } from "@/lib/api/auth";
import { searchStocks } from "@/lib/api/stocks";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  SafeAreaView,
  StyleSheet,
  Text,
  TouchableOpacity,
  useColorScheme,
  View,
  Alert,
  Modal,
  TextInput,
} from "react-native";
import {
  getAutoTradeStatus,
  stopAutoTrade,
  type AutoTradeStatus,
} from "@/lib/api/trade";

// -------------------- 검색 모달 --------------------
function SearchModal({
  visible,
  onClose,
  onSelectStock,
}: {
  visible: boolean;
  onClose: () => void;
  onSelectStock: (symbol: string, name: string) => void;
}) {
  const [searchText, setSearchText] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (text: string) => {
    setSearchText(text);
    setLoading(true);

    try {
      // ✅ text가 "" 여도 그대로 보냄 → 백엔드가 전체 종목 리턴
      const results = await searchStocks(text);
      setSearchResults(results);
    } catch (e) {
      console.error("Search error:", e);
      setSearchResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setSearchText("");
    setSearchResults([]);
    onClose();
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={handleClose}>
      <SafeAreaView style={styles.searchModal}>
        <View style={styles.searchHeader}>
          <TouchableOpacity onPress={handleClose} style={styles.closeButton}>
            <Text style={styles.closeButtonText}>← 닫기</Text>
          </TouchableOpacity>
          <Text style={styles.searchTitle}>종목 검색</Text>
        </View>

        <TextInput
          style={styles.searchInput}
          placeholder="종목명이나 종목코드를 입력하세요"
          value={searchText}
          onChangeText={handleSearch}
          autoFocus={true}
        />

        <FlatList
          data={searchResults}
          keyExtractor={(item) => item.symbol}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.searchResultItem}
              onPress={() => {
                onSelectStock(item.symbol, item.name);
                handleClose();
              }}
            >
              <Text style={styles.stockSymbol}>{item.symbol}</Text>
              <Text style={styles.stockName}>{item.name}</Text>
              <Text style={styles.stockMarket}>{item.market}</Text>
            </TouchableOpacity>
          )}
          ListEmptyComponent={
            searchText.length >= 2 ? (
              <Text style={styles.noResults}>
                {loading ? "검색 중..." : "검색 결과가 없습니다"}
              </Text>
            ) : (
              <Text style={styles.searchHint}>
                종목명 또는 종목코드를 2글자 이상 입력하세요
              </Text>
            )
          }
        />
      </SafeAreaView>
    </Modal>
  );
}

// -------------------- 간단 입력 모달 (빠른 매수) --------------------
function InputModal({
  visible,
  title,
  placeholder,
  onSubmit,
  onCancel,
}: {
  visible: boolean;
  title: string;
  placeholder: string;
  onSubmit: (text: string) => void;
  onCancel: () => void;
}) {
  const [inputText, setInputText] = useState("005930");

  const handleSubmit = () => {
    onSubmit(inputText);
    setInputText("005930");
  };

  const handleCancel = () => {
    onCancel();
    setInputText("005930");
  };

  return (
    <Modal
      visible={visible}
      transparent={true}
      animationType="fade"
      onRequestClose={handleCancel}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <Text style={styles.modalTitle}>{title}</Text>
          <TextInput
            style={styles.modalInput}
            placeholder={placeholder}
            value={inputText}
            onChangeText={setInputText}
            autoCapitalize="none"
            autoFocus={true}
          />
          <View style={styles.modalButtons}>
            <TouchableOpacity
              style={[styles.modalButton, styles.modalCancelButton]}
              onPress={handleCancel}
            >
              <Text style={styles.modalCancelText}>취소</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modalButton, styles.modalSubmitButton]}
              onPress={handleSubmit}
            >
              <Text style={styles.modalSubmitText}>확인</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

// 자동매매 헬퍼 함수 (컴포넌트 외부에 정의)
const startAutoTradeWithAmount = (stockCode: string, stockName: string) => {
  Alert.prompt(
    '투자금액 설정',
    `${stockCode} ${stockName}\n투자금액을 입력하세요 (원)`,
    [
      { text: '취소', style: 'cancel' },
      {
        text: '시작',
        onPress: async (amount? : string) => {
          const investAmount = parseInt(amount || '1000000');
          
          if (isNaN(investAmount) || investAmount < 10000) {
            Alert.alert('오류', '올바른 금액을 입력하세요 (최소 10,000원)');
            return;
          }
          
          try {
            const response = await fetch('http://localhost:8000/auto-trade/start', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                stocks: [stockCode],
                amount_per_stock: investAmount
              }),
            });
            
            const result = await response.json();
            
            if (result.success) {
              Alert.alert('성공', `${stockCode} ${stockName} 자동매매 시작!\n투자금액: ${investAmount.toLocaleString()}원`);
            } else {
              Alert.alert('실패', result.message || '자동매매 시작 실패');
            }
          } catch (error) {
            Alert.alert('오류', '자동매매 시작 요청 실패');
          }
        }
      }
    ],
    'plain-text',
    '1000000'
  );
};

// -------------------- 홈 화면 --------------------
export default function HomeScreen() {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === "dark";
  const router = useRouter();
  const params = useLocalSearchParams();

  const [portfolio, setPortfolio] = useState<PortfolioSnapshot | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  // 연동 상태: null = 확인중, true/false = 확정
  const [linked, setLinked] = useState<boolean | null>(null);

  // 모달 상태
  const [searchModalVisible, setSearchModalVisible] = useState(false);
  const [buyModalVisible, setBuyModalVisible] = useState(false);

  // 자동매매 상태 모달
  const [autoModalVisible, setAutoModalVisible] = useState(false);
  const [autoStatus, setAutoStatus] = useState<AutoTradeStatus | null>(null);
  const [autoStatusLoading, setAutoStatusLoading] = useState(false);

  /** 연동 상태 + 데이터 로드 */
  const load = useCallback(async () => {
    setLinked(null);
    try {
      const keys = await getApiKeys();
      const ok = !!(keys?.appkey && keys?.secretkey);
      setLinked(ok);

      if (ok) {
        try {
          const pf = await getPortfolio();
          setPortfolio(pf);
        } catch (e) {
          console.warn("getPortfolio failed:", e);
          setPortfolio(null);
        }

        try {
          const pos = await getPositions();
          setPositions(pos);
        } catch (e) {
          console.warn("getPositions failed:", e);
          setPositions([]);
        }
      } else {
        setPortfolio(null);
        setPositions([]);
      }
    } catch (e) {
      console.error("getApiKeys failed:", e);
      setLinked(false);
      setPortfolio(null);
      setPositions([]);
    }
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const keys = await getApiKeys();
      const ok = !!(keys?.appkey && keys?.secretkey);
      setLinked(ok);

      if (ok) {
        try {
          const [pf, pos] = await Promise.all([
            getPortfolio().catch((e) => {
              console.warn("getPortfolio failed:", e);
              return null;
            }),
            getPositions().catch((e) => {
              console.warn("getPositions failed:", e);
              return [] as Position[];
            }),
          ]);
          setPortfolio(pf);
          setPositions(pos ?? []);
        } catch {
          // linked 는 그대로
        }
      } else {
        setPortfolio(null);
        setPositions([]);
      }
    } finally {
      setTimeout(() => setRefreshing(false), 500);
    }
  }, []);

  /** 화면 포커스마다 최신 상태 재조회 */
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  /** 저장화면에서 replace("/", { refresh: "1" }) 로 돌아온 경우 처리 */
  useEffect(() => {
    if (params?.refresh) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params?.refresh]);

  // 자동매매 상태 모달 열기
  const openAutoTradeStatus = useCallback(async () => {
    try {
      setAutoStatusLoading(true);
      const status = await getAutoTradeStatus();
      setAutoStatus(status);
      setAutoModalVisible(true);
    } catch (e: any) {
      const msg =
        e?.response?.data?.detail ??
        e?.message ??
        "자동매매 상태를 불러오는 중 오류가 발생했습니다.";
      Alert.alert("오류", msg);
    } finally {
      setAutoStatusLoading(false);
    }
  }, []);

  // 자동매매 중지
  const handleStopAutoTrade = useCallback(async () => {
    try {
      const res = await stopAutoTrade();
      const msg = res?.message ?? "자동매매 중지 요청이 전송되었습니다.";
      Alert.alert("자동매매", msg);
      setAutoStatus({ running: false });
    } catch (e: any) {
      const msg =
        e?.response?.data?.detail ??
        e?.message ??
        "자동매매 중지 중 오류가 발생했습니다.";
      Alert.alert("오류", msg);
    }
  }, []);

  const handleLogout = async () => {
    try {
      await logoutApi();
    } finally {
      router.replace("/(auth)/login"); // 네 라우트 구조에 맞게 경로만 조정
    }
  };

  const bg = isDark ? "#0b0f14" : "#fff";

  return (
    <SafeAreaView
      style={[
        styles.safe,
        { backgroundColor: bg },
        isDark && styles.darkContainer,
      ]}
    >
      {/* 연동 상태 확인 중 */}
      {linked === null && (
        <View style={{ padding: 16 }}>
          <View style={[styles.card, { alignItems: "center" }]}>
            <ActivityIndicator />
            <Text style={[styles.muted, { marginTop: 8 }]}>
              연동 상태 확인 중…
            </Text>
          </View>
        </View>
      )}

      {/* 연동 여부 확정 후 UI */}
      {linked !== null && (
        <>
          {linked ? (
            <>
              <FlatList
                data={[]}
                keyExtractor={() => "dummy"}
                ListHeaderComponent={
                  <>
                    <Header portfolio={portfolio} isDark={isDark} onLogout={handleLogout}/>
                    <QuickActions
                      router={router}
                      onSearchPress={() => setSearchModalVisible(true)}
                      onBuyPress={() => setBuyModalVisible(true)}
                      onAutoTradePress={openAutoTradeStatus}
                      positions={positions}
                    />
                    <PositionsSection positions={positions} isDark={isDark} />
                  </>
                }
                renderItem={() => null}
                refreshControl={
                  <RefreshControl
                    refreshing={refreshing}
                    onRefresh={onRefresh}
                  />
                }
                showsVerticalScrollIndicator={false}
              />

              {/* 종목 검색 모달 */}
              <SearchModal
                visible={searchModalVisible}
                onClose={() => setSearchModalVisible(false)}
                onSelectStock={(symbol, name) =>
                  router.push({
                    pathname: "/trade/[symbol]",
                    params: { symbol, name },
                  })
                }
              />

              {/* 빠른 매수 모달 */}
              <InputModal
                visible={buyModalVisible}
                title="빠른 매수"
                placeholder="매수할 종목 코드를 입력하세요"
                onSubmit={(text) => {
                  setBuyModalVisible(false);
                  if (!text) return;
                  router.push({
                    pathname: "/trade/[symbol]",
                    params: { symbol: text, name: text, side: "BUY" },
                  });
                }}
                onCancel={() => setBuyModalVisible(false)}
              />

              {/* 자동매매 상태 모달 */}
              <Modal
                visible={autoModalVisible}
                transparent
                animationType="fade"
                onRequestClose={() => setAutoModalVisible(false)}
              >
                <View style={styles.autoModalBackdrop}>
                  <View style={styles.autoModalCard}>
                    <Text style={styles.autoModalTitle}>자동 매매 상태</Text>

                    {autoStatusLoading ? (
                      <Text style={styles.autoModalText}>
                        불러오는 중입니다...
                      </Text>
                    ) : autoStatus?.running ? (
                      <>
                        <Text style={styles.autoModalText}>
                          자동매매가 실행 중입니다.
                        </Text>
                        <Text style={styles.autoModalText}>
                          종목: {autoStatus.stocks?.join(", ") || "-"}
                        </Text>
                        <Text style={styles.autoModalText}>
                          종목당 금액:{" "}
                          {autoStatus.amount_per_stock
                            ? `${autoStatus.amount_per_stock.toLocaleString()}원`
                            : "-"}
                        </Text>

                        <View style={styles.autoModalButtonsRow}>
                          <TouchableOpacity
                            style={styles.autoModalStopBtn}
                            onPress={handleStopAutoTrade}
                          >
                            <Text style={styles.autoModalStopText}>
                              자동매매 중지
                            </Text>
                          </TouchableOpacity>
                          <TouchableOpacity
                            style={styles.autoModalCloseBtn}
                            onPress={() => setAutoModalVisible(false)}
                          >
                            <Text style={styles.autoModalCloseText}>
                              닫기
                            </Text>
                          </TouchableOpacity>
                        </View>
                      </>
                    ) : (
                      <>
                        <Text style={styles.autoModalText}>
                          자동매매가 실행 중이 아닙니다.
                        </Text>
                        <TouchableOpacity
                          style={[
                            styles.autoModalCloseBtn,
                            { marginTop: 16 },
                          ]}
                          onPress={() => setAutoModalVisible(false)}
                        >
                          <Text style={styles.autoModalCloseText}>닫기</Text>
                        </TouchableOpacity>
                      </>
                    )}
                  </View>
                </View>
              </Modal>
            </>
          ) : (
            // 미연동 UI
            <FlatList
              ListHeaderComponent={
                <View style={[styles.card, { margin: 16 }]}>
                  <Text
                    style={{
                      fontSize: 18,
                      fontWeight: "800",
                      marginBottom: 6,
                    }}
                  >
                    계좌 연동 필요
                  </Text>
                  <Text style={styles.muted}>
                    계좌를 연결하면 보유 종목과 손익이 표시됩니다.
                  </Text>
                  <TouchableOpacity
                    style={styles.linkBtn}
                    onPress={() => router.push("/settings/account-link")}
                    activeOpacity={0.85}
                  >
                    <Text style={styles.linkBtnTx}>계좌 연동하기</Text>
                  </TouchableOpacity>
                  <Text style={[styles.muted, { marginTop: 6 }]}>
                    계좌 연동이 아직 설정되지 않았습니다.
                  </Text>
                </View>
              }
              data={[]}
              keyExtractor={() => "dummy"}
              contentContainerStyle={{ paddingBottom: 24 }}
              renderItem={() => null}
              refreshControl={
                <RefreshControl
                  refreshing={refreshing}
                  onRefresh={onRefresh}
                />
              }
              showsVerticalScrollIndicator={false}
            />
          )}
        </>
      )}
    </SafeAreaView>
  );
}

// -------------------- 헤더 --------------------
function Header({
  portfolio,
  isDark,
  onLogout,
}: {
  portfolio: PortfolioSnapshot | null;
  isDark: boolean;
  onLogout: () => void;
}) {
  const totalEquity = useMemo(() => {
    if (!portfolio?.totalEquity) return "0";
    return formatKRW(portfolio.totalEquity);
  }, [portfolio]);

  const pnlDay = useMemo(() => {
    if (!portfolio?.pnlDay) return { text: "0", isPositive: true };
    const val = parseFloat(portfolio.pnlDay);
    return {
      text: formatKRW(portfolio.pnlDay),
      isPositive: val >= 0,
    };
  }, [portfolio]);

  const pnlDayPct = useMemo(() => {
    if (!portfolio?.pnlDayPct) return { text: "0.00%", isPositive: true };
    const val = parseFloat(portfolio.pnlDayPct);
    return {
      text: `${(val * 100).toFixed(2)}%`,
      isPositive: val >= 0,
    };
  }, [portfolio]);


  return (
    <View style={styles.header}>
      <View style={styles.headerTopRow}>
        <Text style={[styles.greeting, isDark && styles.darkText]}>
          안녕하세요 DQN 기반 트레이딩 봇입니다
        </Text>
        <TouchableOpacity onPress={onLogout}>
          <Text style={styles.logoutText}>로그아웃</Text>
        </TouchableOpacity>
      </View>

      <Text style={[styles.totalEquity, isDark && styles.darkText]}>
        {totalEquity}
      </Text>
      <View style={styles.pnlRow}>
        {/* 기존 pnl 표시 그대로 */}
      </View>
    </View>
  );
}

// -------------------- 퀵 액션 --------------------
function QuickActions({
  router,
  positions,
  onSearchPress,
  onBuyPress,
  onAutoTradePress,
}: {
  router: any;
  positions: Position[];
  onSearchPress: () => void;
  onBuyPress: () => void;
  onAutoTradePress?: () => void; // 옵션으로 두고, 없으면 fallback
}) {
  const Item = ({
    icon,
    label,
    onPress,
  }: {
    icon: React.ReactNode;
    label: string;
    onPress?: () => void;
  }) => (
    <TouchableOpacity style={styles.qaItem} onPress={onPress}>
      <View style={styles.qaIcon}>{icon}</View>
      <Text style={styles.qaLabel}>{label}</Text>
    </TouchableOpacity>
  );

  // ✅ 빠른 매도: props로 받은 positions 사용
  const handleQuickSell = () => {
    if (!positions || positions.length === 0) {
      Alert.alert("알림", "보유 종목이 없습니다.");
      return;
    }

    const options = positions.slice(0, 3).map((pos) => ({
      text: `${pos.symbol} (${pos.name}) - ${pos.qty}주`,
      onPress: () => {
        router.push({
          pathname: "/trade/[symbol]",
          params: { symbol: pos.symbol, name: pos.name, side: "SELL" },
        });
      },
    }));

    Alert.alert("빠른 매도", "매도할 종목을 선택하세요", [
      { text: "취소", style: "cancel" },
      ...options,
    ]);
  };

  // ✅ 자동매매 버튼: 콜백이 있으면 그걸 호출, 없으면 기본 안내만
  const handleAutoTrade = () => {
    if (onAutoTradePress) {
      onAutoTradePress();
      return;
    }

    Alert.alert(
      "자동매매",
      "자동매매 관리 기능이 아직 연결되지 않았습니다.\n" +
        "필요하면 onAutoTradePress 콜백에 구현해 주세요."
    );
  };

  return (
    <View style={styles.qaWrap}>
      <Item
        icon={<Feather name="search" size={24} color="#6b7280" />}
        label="종목검색"
        onPress={onSearchPress}
      />
      <Item
        icon={<MaterialCommunityIcons name="plus-circle" size={24} color="#16a34a" />}
        label="빠른매수"
        onPress={onBuyPress}
      />
      <Item
        icon={<MaterialCommunityIcons name="minus-circle" size={24} color="#dc2626" />}
        label="빠른매도"
        onPress={handleQuickSell}
      />
      <Item
        icon={<MaterialCommunityIcons name="robot" size={24} color="#0ea5e9" />}
        label="자동매매"
        onPress={handleAutoTrade}
      />
      <Item
        icon={<MaterialCommunityIcons name="credit-card-settings-outline" size={24} color="#6366f1" />}
        label="계좌설정"
        onPress={() => router.push("/settings/account-link")}
      />
    </View>
  );
}


// -------------------- 보유 종목 섹션 --------------------
function PositionsSection({
  positions,
  isDark,
}: {
  positions: Position[];
  isDark: boolean;
}) {
  const router = useRouter();

  const PositionItem = ({ item }: { item: Position }) => {
    const pnl = parseFloat(item.pnl);
    const isPositive = pnl >= 0;

    return (
      <TouchableOpacity
        style={[styles.posItem, isDark && styles.darkPosItem]}
        onPress={() =>
          router.push({
            pathname: "/trade/[symbol]",
            params: { symbol: item.symbol, name: item.name },
          })
        }
      >
        <View style={styles.posLeft}>
          <Text style={[styles.posSymbol, isDark && styles.darkText]}>
            {item.symbol}
          </Text>
          <Text style={[styles.posName, isDark && styles.darkSubText]}>
            {item.name}
          </Text>
          <Text style={[styles.posQty, isDark && styles.darkSubText]}>
            {item.qty}주
          </Text>
        </View>
        <View style={styles.posRight}>
          <Text style={[styles.posPrice, isDark && styles.darkText]}>
            {formatKRW(item.lastPrice)}
          </Text>
          <Text
            style={[
              styles.posPnl,
              isPositive ? styles.positiveText : styles.negativeText,
            ]}
          >
            {isPositive ? "+" : ""}
            {formatKRW(item.pnl)} ({isPositive ? "+" : ""}
            {(parseFloat(item.pnlPct) * 100).toFixed(2)}%)
          </Text>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.posSection}>
      <Text style={[styles.sectionTitle, isDark && styles.darkText]}>
        보유 종목 ({positions.length})
      </Text>
      {positions.length === 0 ? (
        <Text style={[styles.emptyText, isDark && styles.darkSubText]}>
          보유 종목이 없습니다
        </Text>
      ) : (
        positions.map((item, index) => (
          <PositionItem key={`${item.symbol}-${index}`} item={item} />
        ))
      )}
    </View>
  );
}

// -------------------- 유틸/스타일 --------------------
function formatKRW(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "0";
  return new Intl.NumberFormat("ko-KR").format(Math.round(num));
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#ffffff",
  },
  darkContainer: {
    backgroundColor: "#000000",
  },
  header: {
    padding: 24,
    paddingBottom: 16,
  },
  greeting: {
    fontSize: 16,
    color: "#6b7280",
    marginBottom: 8,
  },
  totalEquity: {
    fontSize: 32,
    fontWeight: "bold",
    color: "#111827",
    marginBottom: 4,
  },
  pnlRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  pnlText: {
    fontSize: 16,
    fontWeight: "600",
  },
  positiveText: {
    color: "#16a34a",
  },
  negativeText: {
    color: "#dc2626",
  },
  qaWrap: {
    flexDirection: "row",
    paddingHorizontal: 24,
    paddingBottom: 16,
    justifyContent: "space-between",
  },
  qaItem: {
    alignItems: "center",
    flex: 1,
  },
  qaIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#f3f4f6",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
  },
  qaLabel: {
    fontSize: 12,
    color: "#6b7280",
    textAlign: "center",
    fontWeight: "500",
  },
  posSection: {
    flex: 1,
    paddingHorizontal: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#111827",
    marginBottom: 16,
  },
  emptyText: {
    color: "#9ca3af",
    textAlign: "center",
    marginTop: 32,
    fontSize: 16,
  },
  posItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 16,
    paddingHorizontal: 16,
    backgroundColor: "#f8fafc",
    borderRadius: 12,
    marginBottom: 8,
  },
  darkPosItem: {
    backgroundColor: "#1f2937",
  },
  posLeft: {
    flex: 1,
  },
  posSymbol: {
    fontSize: 16,
    fontWeight: "bold",
    color: "#111827",
    marginBottom: 2,
  },
  posName: {
    fontSize: 14,
    color: "#6b7280",
    marginBottom: 2,
  },
  posQty: {
    fontSize: 12,
    color: "#9ca3af",
  },
  posRight: {
    alignItems: "flex-end",
  },
  posPrice: {
    fontSize: 16,
    fontWeight: "bold",
    color: "#111827",
    marginBottom: 2,
  },
  posPnl: {
    fontSize: 14,
    fontWeight: "600",
  },
  darkText: {
    color: "#f9fafb",
  },
  darkSubText: {
    color: "#d1d5db",
  },

  // 검색 모달 스타일
  searchModal: {
    flex: 1,
    backgroundColor: "white",
  },
  searchHeader: {
    flexDirection: "row",
    alignItems: "center",
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#e5e7eb",
  },
  closeButton: {
    marginRight: 16,
  },
  closeButtonText: {
    fontSize: 16,
    color: "#2563eb",
  },
  searchTitle: {
    fontSize: 18,
    fontWeight: "bold",
  },
  searchInput: {
    margin: 16,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 8,
    fontSize: 16,
  },
  searchResultItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#f3f4f6",
  },
  stockSymbol: {
    fontSize: 16,
    fontWeight: "bold",
    width: 80,
  },
  stockName: {
    fontSize: 14,
    flex: 1,
    marginHorizontal: 12,
  },
  stockMarket: {
    fontSize: 12,
    color: "#6b7280",
    backgroundColor: "#f3f4f6",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  noResults: {
    textAlign: "center",
    marginTop: 40,
    fontSize: 16,
    color: "#6b7280",
  },
  searchHint: {
    textAlign: "center",
    marginTop: 40,
    fontSize: 14,
    color: "#9ca3af",
  },

  // 간단한 입력 모달 스타일
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "center",
    alignItems: "center",
  },
  modalContent: {
    backgroundColor: "white",
    borderRadius: 16,
    padding: 24,
    width: "80%",
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "bold",
    textAlign: "center",
    marginBottom: 16,
    color: "#111827",
  },
  modalInput: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    marginBottom: 20,
  },
  modalButtons: {
    flexDirection: "row",
    gap: 12,
  },
  modalButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  modalCancelButton: {
    backgroundColor: "#f3f4f6",
  },
  modalSubmitButton: {
    backgroundColor: "#2563eb",
  },
  modalCancelText: {
    color: "#6b7280",
    fontWeight: "600",
  },
  modalSubmitText: {
    color: "white",
    fontWeight: "600",
  },

  safe: { flex: 1 },
  muted: { color: "#6b7280" },

  card: {
    backgroundColor: "#f8fafc",
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },

  // 계좌 연동 버튼
  linkBtn: {
    marginTop: 12,
    backgroundColor: "#111827",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  linkBtnTx: { color: "#fff", fontWeight: "800" },

  // 자동매매 상태 모달
  autoModalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.3)",
    alignItems: "center",
    justifyContent: "center",
  },
  autoModalCard: {
    width: "80%",
    maxWidth: 400,
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 20,
  },
  autoModalTitle: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 12,
  },
  autoModalText: {
    fontSize: 14,
    marginBottom: 4,
  },
  autoModalButtonsRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    marginTop: 16,
    gap: 8,
  },
  autoModalStopBtn: {
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    backgroundColor: "#dc2626",
  },
  autoModalStopText: {
    color: "#fff",
    fontWeight: "700",
  },
  autoModalCloseBtn: {
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    backgroundColor: "#e5e7eb",
  },
  autoModalCloseText: {
    fontWeight: "700",
    color: "#111827",
  },
    headerTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  logoutText: {
    fontSize: 14,
    color: "#6b7280",
    fontWeight: "600",
  },
});

