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
  Alert,
  Modal,
  TextInput,
} from "react-native";

// 검색 모달 컴포넌트
function SearchModal({
  visible,
  onClose,
  onSelectStock,
}: {
  visible: boolean;
  onClose: () => void;
  onSelectStock: (symbol: string, name: string) => void;
}) {
  const [searchText, setSearchText] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (text: string) => {
    setSearchText(text);
    if (text.length < 2) {
      setSearchResults([]);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/search/stocks?q=${encodeURIComponent(text)}`);
      const results = await response.json();
      setSearchResults(results);
    } catch (error) {
      console.error('Search error:', error);
      setSearchResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setSearchText('');
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
                {loading ? '검색 중...' : '검색 결과가 없습니다'}
              </Text>
            ) : (
              <Text style={styles.searchHint}>종목명 또는 종목코드를 2글자 이상 입력하세요</Text>
            )
          }
        />
      </SafeAreaView>
    </Modal>
  );
}

// 간단한 입력 모달 
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
  const [inputText, setInputText] = useState('005930');

  const handleSubmit = () => {
    console.log(`InputModal Submit: ${inputText}`);
    onSubmit(inputText);
    setInputText('005930');
  };

  const handleCancel = () => {
    onCancel();
    setInputText('005930');
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
        onPress: async (amount) => {
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

export default function HomeScreen() {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === "dark";
  const router = useRouter();

  const [portfolio, setPortfolio] = useState<PortfolioSnapshot | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(false);
  
  // 모달 상태들
  const [searchModalVisible, setSearchModalVisible] = useState(false);
  const [buyModalVisible, setBuyModalVisible] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [portfolioData, positionsData] = await Promise.all([
        getPortfolio(),
        getPositions(),
      ]);
      setPortfolio(portfolioData);
      setPositions(positionsData);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 검색 결과 선택 처리
  const handleSearchSelect = (symbol: string, name: string) => {
    router.push({
      pathname: "/symbol/[symbol]", // 수정: trade → symbol
      params: { symbol, name },
    });
  };

  // 빠른 매수 처리 함수
  const handleBuy = (text: string) => {
    console.log(`Quick Buy: ${text}`);
    setBuyModalVisible(false);
    if (!text) return;
    router.push({
      pathname: "/symbol/[symbol]", // 수정: trade → symbol
      params: { symbol: text, name: text, side: 'BUY' },
    });
  };

  return (
    <SafeAreaView style={[styles.container, isDark && styles.darkContainer]}>
      <FlatList
        data={[]}
        keyExtractor={() => "dummy"}
        ListHeaderComponent={
          <>
            <Header portfolio={portfolio} isDark={isDark} />
            <QuickActions
              router={router}
              onSearchPress={() => setSearchModalVisible(true)}
              onBuyPress={() => setBuyModalVisible(true)}
            />
            <PositionsSection positions={positions} isDark={isDark} />
          </>
        }
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={fetchData} />
        }
        showsVerticalScrollIndicator={false}
      />

      {/* 검색 모달 */}
      <SearchModal
        visible={searchModalVisible}
        onClose={() => setSearchModalVisible(false)}
        onSelectStock={handleSearchSelect}
      />

      {/* 빠른 매수 모달 */}
      <InputModal
        visible={buyModalVisible}
        title="빠른 매수"
        placeholder="매수할 종목 코드를 입력하세요"
        onSubmit={handleBuy}
        onCancel={() => setBuyModalVisible(false)}
      />
    </SafeAreaView>
  );
}

function Header({
  portfolio,
  isDark,
}: {
  portfolio: PortfolioSnapshot | null;
  isDark: boolean;
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
      <Text style={[styles.greeting, isDark && styles.darkText]}>
        Good afternoon
      </Text>
      <Text style={[styles.totalEquity, isDark && styles.darkText]}>
        {totalEquity}
      </Text>
      <View style={styles.pnlRow}>
        <Text
          style={[
            styles.pnlText,
            pnlDay.isPositive ? styles.positiveText : styles.negativeText,
          ]}
        >
          {pnlDay.isPositive ? "+" : ""}
          {pnlDay.text}
        </Text>
        <Text
          style={[
            styles.pnlText,
            pnlDayPct.isPositive ? styles.positiveText : styles.negativeText,
          ]}
        >
          ({pnlDayPct.isPositive ? "+" : ""}
          {pnlDayPct.text})
        </Text>
      </View>
    </View>
  );
}

function QuickActions({
  router,
  onSearchPress,
  onBuyPress,
}: {
  router: any;
  onSearchPress: () => void;
  onBuyPress: () => void;
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

  // 빠른 매도 함수  
  const handleQuickSell = async () => {
    try {
      const response = await fetch('http://localhost:8000/positions');
      const positions = await response.json();
      
      if (positions.length === 0) {
        Alert.alert('알림', '보유 종목이 없습니다.');
        return;
      }

      const options = positions.map((pos: any) => ({
        text: `${pos.symbol} (${pos.name}) - ${pos.qty}주`,
        onPress: () => {
          router.push({
            pathname: "/symbol/[symbol]", // 수정: trade → symbol
            params: { symbol: pos.symbol, name: pos.name, side: 'SELL' },
          });
        },
      }));

      Alert.alert(
        '빠른 매도',
        '매도할 종목을 선택하세요',
        [
          { text: '취소', style: 'cancel' },
          ...options.slice(0, 3),
        ]
      );
    } catch (error) {
      Alert.alert('오류', '보유 종목 조회에 실패했습니다.');
    }
  };

  // 🔴 개선된 자동매매 관리 함수
  const handleBotManage = async () => {
    console.log('Bot Manage button pressed');
    
    try {
      const response = await fetch('http://localhost:8000/auto-trade/status');
      const status = await response.json();
      
      console.log('Auto trade status:', status);
      
      if (status.running && status.stocks.length > 0) {
        // 실행 중인 경우 - 중지 옵션 제공
        Alert.alert(
          '자동매매 관리',
          `현재 ${status.count}개 종목으로 자동매매 실행 중\n종목: ${status.stocks.join(', ')}\n투자금액: ${status.amount_per_stock?.toLocaleString() || 'N/A'}원/종목`,
          [
            { text: '취소', style: 'cancel' },
            {
              text: '중지',
              style: 'destructive',
              onPress: async () => {
                console.log('Stopping auto trade...');
                try {
                  const stopResponse = await fetch('http://localhost:8000/auto-trade/stop', {
                    method: 'POST',
                  });
                  const result = await stopResponse.json();
                  
                  console.log('Stop auto trade result:', result);
                  
                  if (result.success) {
                    Alert.alert('성공', '자동매매가 중지되었습니다.');
                  } else {
                    Alert.alert('실패', '자동매매 중지에 실패했습니다.');
                  }
                } catch (error) {
                  console.error('Stop auto trade error:', error);
                  Alert.alert('오류', '자동매매 중지 요청 실패');
                }
              },
            },
          ]
        );
      } else {
        // 실행 중이 아닌 경우 - 개선된 시작 옵션 제공
        console.log('Auto trade not running, showing alert');
        Alert.alert(
          '자동매매 시작',
          '어떤 방법으로 시작하시겠습니까?',
          [
            { text: '취소', style: 'cancel' },
            {
              text: '종목 검색하여 선택',
              onPress: () => {
                Alert.alert('알림', '종목 검색 → 개별 종목 페이지에서 자동매매 버튼을 사용하세요.');
                onSearchPress();
              },
            },
            {
              text: '직접 종목코드 입력',
              onPress: () => {
                Alert.prompt(
                  '종목코드 입력',
                  '자동매매할 종목코드를 입력하세요 (예: 005930)',
                  [
                    { text: '취소', style: 'cancel' },
                    {
                      text: '다음',
                      onPress: (stockCode) => {
                        if (!stockCode || stockCode.length !== 6) {
                          Alert.alert('오류', '올바른 6자리 종목코드를 입력하세요');
                          return;
                        }
                        
                        Alert.prompt(
                          '투자금액 설정',
                          `${stockCode} 종목 투자금액을 입력하세요 (원)`,
                          [
                            { text: '취소', style: 'cancel' },
                            {
                              text: '시작',
                              onPress: async (amount) => {
                                const investAmount = parseInt(amount || '1000000');
                                
                                if (isNaN(investAmount) || investAmount < 10000) {
                                  Alert.alert('오류', '올바른 금액을 입력하세요 (최소 10,000원)');
                                  return;
                                }
                                
                                try {
                                  const startResponse = await fetch('http://localhost:8000/auto-trade/start', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                      stocks: [stockCode],
                                      amount_per_stock: investAmount
                                    }),
                                  });
                                  
                                  const result = await startResponse.json();
                                  
                                  if (result.success) {
                                    Alert.alert('성공', `${stockCode} 종목으로 자동매매가 시작되었습니다!\n투자금액: ${investAmount.toLocaleString()}원`);
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
                      }
                    }
                  ],
                  'plain-text',
                  '005930'
                );
              },
            },
            {
              text: '인기 종목으로 빠른 시작',
              onPress: () => {
                Alert.alert(
                  '인기 종목 선택',
                  '빠른 시작할 종목을 선택하세요',
                  [
                    { text: '취소', style: 'cancel' },
                    {
                      text: '005930 (삼성전자)',
                      onPress: () => startAutoTradeWithAmount('005930', '삼성전자'),
                    },
                    {
                      text: '000660 (SK하이닉스)', 
                      onPress: () => startAutoTradeWithAmount('000660', 'SK하이닉스'),
                    },
                    {
                      text: '035720 (카카오)', 
                      onPress: () => startAutoTradeWithAmount('035720', '카카오'),
                    },
                  ]
                );
              },
            },
          ]
        );
      }
    } catch (error) {
      console.error('Get auto trade status error:', error);
      Alert.alert('오류', '자동매매 상태 확인에 실패했습니다.');
    }
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
        onPress={handleBotManage}
      />
    </View>
  );
}

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
            pathname: "/symbol/[symbol]", // 수정: trade → symbol
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
    backgroundColor: 'white',
  },
  searchHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  closeButton: {
    marginRight: 16,
  },
  closeButtonText: {
    fontSize: 16,
    color: '#2563eb',
  },
  searchTitle: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  searchInput: {
    margin: 16,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
    fontSize: 16,
  },
  searchResultItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f3f4f6',
  },
  stockSymbol: {
    fontSize: 16,
    fontWeight: 'bold',
    width: 80,
  },
  stockName: {
    fontSize: 14,
    flex: 1,
    marginHorizontal: 12,
  },
  stockMarket: {
    fontSize: 12,
    color: '#6b7280',
    backgroundColor: '#f3f4f6',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  noResults: {
    textAlign: 'center',
    marginTop: 40,
    fontSize: 16,
    color: '#6b7280',
  },
  searchHint: {
    textAlign: 'center',
    marginTop: 40,
    fontSize: 14,
    color: '#9ca3af',
  },

  // 간단한 입력 모달 스타일
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    backgroundColor: 'white',
    borderRadius: 16,
    padding: 24,
    width: '80%',
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 16,
    color: '#111827',
  },
  modalInput: {
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    marginBottom: 20,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  modalButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  modalCancelButton: {
    backgroundColor: '#f3f4f6',
  },
  modalSubmitButton: {
    backgroundColor: '#2563eb',
  },
  modalCancelText: {
    color: '#6b7280',
    fontWeight: '600',
  },
  modalSubmitText: {
    color: 'white',
    fontWeight: '600',
  },
});
