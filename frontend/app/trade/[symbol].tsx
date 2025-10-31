import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Dimensions,
  Platform,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  Modal,
} from "react-native";
import Chart from "../../components/Chart";

const API_BASE = 'http://localhost:8000';
const { width: screenWidth } = Dimensions.get('window');

type OrderSide = "BUY" | "SELL";
type OrderType = "MARKET" | "LIMIT";

interface Quote {
  symbol: string;
  name?: string;
  price: number;
  changePct: number;
}

export default function SymbolScreen() {
  const { symbol, name, side } = useLocalSearchParams<{
    symbol: string;
    name?: string;
    side?: OrderSide;
  }>();

  const router = useRouter();

  const [quote, setQuote] = useState<Quote>({
    symbol: symbol ?? '005930',
    name: name || '종목',
    price: 0,
    changePct: 0.0,
  });

  const [chart, setChart] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [autoTradeActive, setAutoTradeActive] = useState(false);
  const [priceError, setPriceError] = useState(false);
  const [chartDimensions, setChartDimensions] = useState({ width: 0, height: 0 });
  
  // 금액 입력 모달 관련 상태 추가
  const [amountModalVisible, setAmountModalVisible] = useState(false);
  const [inputAmount, setInputAmount] = useState('1000000');

  // 실시간 시세 업데이트
  useEffect(() => {
    const fetchPrice = async () => {
      try {
        const response = await fetch(`${API_BASE}/quote/${symbol ?? '005930'}`);
        const data = await response.json();
        const priceStr = data.price;
        const changePctStr = data.changePct;

        const price = Number(priceStr);
        const changePct = Number(changePctStr) || 0;

        if (price > 0 && !isNaN(price)) {
          setQuote(prev => ({ ...prev, price, changePct }));
          setPriceError(false);
        } else {
          setPriceError(true);
        }
      } catch (error: any) {
        console.error('Price fetch error:', error);
        setPriceError(true);
      }
    };

    fetchPrice();
    const id = setInterval(fetchPrice, 3000);
    return () => clearInterval(id);
  }, [symbol]);

  // 차트 데이터 로드
  useEffect(() => {
    const fetchChart = async () => {
      if (loading) return;
      setLoading(true);
      try {
        const response = await fetch(`${API_BASE}/chart`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ symbol: symbol ?? '005930' }),
        });
        const data = await response.json();
        setChart(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Chart fetch error:', error);
        setChart([]);
      } finally {
        setLoading(false);
      }
    };

    fetchChart();
  }, [symbol]);

  // 자동매매 상태 실시간 체크
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await fetch(`${API_BASE}/auto-trade/status`);
        const data = await response.json();
        
        const isRunning = data.running;
        const stocks = data.stocks || [];
        const newActive = isRunning && stocks.includes(symbol ?? '005930');
        
        if (newActive !== autoTradeActive) {
          setAutoTradeActive(newActive);
        }
      } catch (error) {
        console.error('Auto trade status error:', error);
      }
    };

    checkStatus();
    const id = setInterval(checkStatus, 3000);
    return () => clearInterval(id);
  }, [symbol, autoTradeActive]);

  // 자동매매 시작 실행 함수 
  const startAutoTradeWithAmount = async (sym: string, amount: number) => {
    try {
      console.log(`Starting auto trade for ${sym} with ${amount.toLocaleString()}원`);
      
      const response = await fetch(`${API_BASE}/auto-trade/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stocks: [sym],
          amount_per_stock: amount  // 금액 설정 추가
        })
      });
      
      console.log(`Response status: ${response.status}`);
      const result = await response.json();
      console.log(`Response data:`, result);
      
      if (result.success) {
        setAutoTradeActive(true);
        Alert.alert(
          '자동매매 시작!', 
          `종목: ${sym}\n투자금액: ${amount.toLocaleString()}원\n\n매도 에이전트 → 매수 에이전트 순으로 실행됩니다.`
        );
      } else {
        Alert.alert('실패', result.message || '자동매매 시작 실패');
      }
    } catch (error: any) {
      console.error('Auto trade start error:', error);
      Alert.alert('오류', '자동매매 시작 요청 실패');
    }
  };

  // 자동매매 시작/중지 함수 (금액 설정 포함)
  const handleAutoTrade = async (sym: string) => {
    console.log(`Auto trade button clicked for ${sym}, current active: ${autoTradeActive}`);
    
    if (autoTradeActive) {
      // 현재 실행 중이면 중지
      try {
        console.log('Stopping auto trade...');
        const response = await fetch(`${API_BASE}/auto-trade/stop`, {
          method: 'POST',
        });
        const result = await response.json();
        console.log('Stop response:', result);
        
        if (result.success) {
          setAutoTradeActive(false);
          Alert.alert('성공', `${sym} 자동매매가 중지되었습니다.`);
        } else {
          Alert.alert('실패', result.message || '자동매매 중지 실패');
        }
      } catch (error: any) {
        console.error('Auto trade stop error:', error);
        Alert.alert('오류', '자동매매 중지 요청 실패');
      }
    } else {
      // 현재 중지 상태면 시작 - 금액 입력 모달 열기
      console.log('Opening amount input modal...');
      setInputAmount('1000000'); // 기본값 100만원
      setAmountModalVisible(true);
    }
  };

  const changePctColor = quote.changePct > 0 ? '#16a34a' : quote.changePct < 0 ? '#dc2626' : '#6b7280';
  const changePctSign = quote.changePct > 0 ? '+' : '';

  const onLayout = useCallback((event: any) => {
    const { width, height } = event.nativeEvent.layout;
    if (width > 0 && height > 0) {
      setChartDimensions({ width, height: Math.max(height, 200) });
    }
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Feather name="chevron-left" size={24} color="#333" />
          </TouchableOpacity>
          <View style={styles.headerContent}>
            <Text style={styles.symbolText} numberOfLines={1}>
              {quote.symbol} {quote.name && `• ${quote.name}`}
            </Text>
            <View style={styles.priceRow}>
              {priceError ? (
                <Text style={styles.errorText}>가격 조회 실패</Text>
              ) : (
                <>
                  <Text style={styles.priceText}>
                    {quote.price.toLocaleString()}
                  </Text>
                  <Text style={[styles.changePctText, { color: changePctColor }]}>
                    {changePctSign}{(quote.changePct * 100).toFixed(2)}%
                  </Text>
                </>
              )}
            </View>
          </View>
        </View>

        <View style={styles.chartContainer} onLayout={onLayout}>
          <Text style={styles.chartTitle}>차트</Text>
          <View style={styles.chartWrapper}>
            <Chart data={chart} />
          </View>
        </View>

        <OrderPanel 
          symbol={quote.symbol} 
          lastPrice={quote.price} 
          initialSide={side}
          onAutoTrade={handleAutoTrade}
          autoTradeActive={autoTradeActive}
        />
      </ScrollView>

      {/* 금액 입력 모달 */}
      <Modal
        visible={amountModalVisible}
        transparent={true}
        animationType="fade"
        onRequestClose={() => setAmountModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>자동매매 시작</Text>
            <Text style={styles.modalSubtitle}>{quote.symbol} 종목 투자금액 설정</Text>
            
            <TextInput
              style={styles.modalInput}
              placeholder="투자금액 (원)"
              value={inputAmount}
              onChangeText={setInputAmount}
              keyboardType="numeric"
              autoFocus={true}
            />
            
            <View style={styles.quickAmountButtons}>
              {[
                { label: '10만원', value: '100000' },
                { label: '50만원', value: '500000' },
                { label: '100만원', value: '1000000' },
                { label: '500만원', value: '5000000' },
              ].map((item) => (
                <TouchableOpacity
                  key={item.value}
                  style={styles.quickAmountBtn}
                  onPress={() => setInputAmount(item.value)}
                >
                  <Text style={styles.quickAmountText}>{item.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
            
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalButton, styles.modalCancelButton]}
                onPress={() => setAmountModalVisible(false)}
              >
                <Text style={styles.modalCancelText}>취소</Text>
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[styles.modalButton, styles.modalSubmitButton]}
                onPress={async () => {
                  const amount = parseInt(inputAmount);
                  setAmountModalVisible(false);
                  
                  if (isNaN(amount) || amount < 10000) {
                    Alert.alert('오류', '올바른 금액을 입력하세요\n(최소 10,000원)');
                    return;
                  }
                  
                  if (amount > 100000000) {
                    Alert.alert('확인', '1억원을 초과하는 금액입니다.\n정말 진행하시겠습니까?', [
                      { text: '취소', style: 'cancel' },
                      { text: '진행', onPress: () => startAutoTradeWithAmount(quote.symbol, amount) }
                    ]);
                  } else {
                    await startAutoTradeWithAmount(quote.symbol, amount);
                  }
                }}
              >
                <Text style={styles.modalSubmitText}>시작</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

interface OrderPanelProps {
  symbol: string;
  lastPrice: number;
  initialSide?: OrderSide;
  onAutoTrade: (symbol: string) => void;
  autoTradeActive: boolean;
}

function OrderPanel({ symbol, lastPrice, initialSide, onAutoTrade, autoTradeActive }: OrderPanelProps) {
  const [side, setSide] = useState<OrderSide>(initialSide || "BUY");
  const [type, setType] = useState<OrderType>("LIMIT");
  const [price, setPrice] = useState(String(lastPrice));
  const [qty, setQty] = useState("1");

  useEffect(() => {
    if (lastPrice > 0 && type === "LIMIT") {
      setPrice(String(lastPrice));
    }
  }, [lastPrice, type]);

  const notional = useMemo(() => {
    const priceToUse = type === "MARKET" ? lastPrice : Number(price || 0);
    return priceToUse * Number(qty || 0);
  }, [type, price, qty, lastPrice]);

  const canSubmit = Number(qty) > 0 && (type === "MARKET" || Number(price) > 0);

  const onTick = (dir: 1 | -1) => {
    const p = Number(price || 0);
    const next = Math.max(0, p + dir * 100);
    setPrice(String(next));
  };

  const submit = async () => {
    if (!canSubmit) return;

    try {
      const orderData = {
        symbol: symbol,
        side: side,
        type: type,
        price: type === "MARKET" ? 0 : Number(price),
        qty: Number(qty)
      };

      const response = await fetch(`${API_BASE}/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orderData),
      });

      const result = await response.json();

      if (result.success) {
        Alert.alert(
          "주문 성공",
          `${symbol} ${side === "BUY" ? "매수" : "매도"} 주문이 전송되었습니다.`,
          [{ text: "확인" }]
        );
      } else {
        Alert.alert("주문 실패", result.message || "주문 전송에 실패했습니다.");
      }
    } catch (error) {
      console.error('Order error:', error);
      Alert.alert("오류", "주문 전송 중 오류가 발생했습니다.");
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
          <Text style={[styles.sideTabText, side === "BUY" && styles.sideTabTextActive]}>
            매수
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.sideTab, side === "SELL" && styles.sideTabActiveSell]}
          onPress={() => setSide("SELL")}
        >
          <Text style={[styles.sideTabText, side === "SELL" && styles.sideTabTextActive]}>
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

      <View style={{ gap: 10 }}>
        <Field label="가격">
          {type === "MARKET" ? (
            <View style={styles.inline}>
              <Text style={styles.marketPrice}>
                {lastPrice.toLocaleString()} (시장가)
              </Text>
            </View>
          ) : (
            <View style={styles.priceRowInner}>
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
            {["1", "5", "10", "20"].map((q) => (
              <TouchableOpacity key={q} style={styles.qtyPill} onPress={() => setQty(q)}>
                <Text style={styles.qtyPillText}>{q}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </Field>

        <View style={styles.summary}>
          <Text style={styles.summaryKey}>예상 주문금액</Text>
          <Text style={styles.summaryVal}>
            {notional.toLocaleString()} KRW
          </Text>
        </View>

        {/* 일반 주문 버튼 */}
        <TouchableOpacity
          style={[
            styles.submitBtn,
            !canSubmit && { opacity: 0.5 },
            side === "BUY" ? styles.buyBtn : styles.sellBtn
          ]}
          onPress={submit}
          disabled={!canSubmit}
          activeOpacity={0.8}
        >
          <Text style={styles.submitText}>
            {side === "BUY" ? "매수 주문" : "매도 주문"}
          </Text>
        </TouchableOpacity>

        {/* 자동매매 버튼 */}
        <TouchableOpacity
          style={[
            styles.autoBtn,
            autoTradeActive && styles.autoBtnActive
          ]}
          onPress={() => onAutoTrade(symbol)}
          activeOpacity={0.85}
        >
          <MaterialCommunityIcons 
            name={autoTradeActive ? "stop-circle" : "robot"} 
            size={20} 
            color="white" 
          />
          <Text style={styles.autoBtnText}>
            {autoTradeActive ? '자동매매 중지' : '자동매매 시작'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

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
            <Text style={[styles.toggleText, active && styles.toggleTextActive]}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  scrollView: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  backButton: {
    marginRight: 12,
  },
  headerContent: {
    flex: 1,
  },
  symbolText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  priceText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
  },
  changePctText: {
    fontSize: 16,
    fontWeight: '600',
  },
  errorText: {
    fontSize: 16,
    color: '#dc2626',
    fontWeight: '500',
  },
  chartContainer: {
    padding: 16,
  },
  chartTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 12,
    color: '#333',
  },
  chartWrapper: {
    backgroundColor: '#f8f9fa',
    borderRadius: 12,
    padding: 8,
    minHeight: 200,
  },
  orderCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    margin: 16,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  sideTabs: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  sideTab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    backgroundColor: '#fff',
  },
  sideTabActiveBuy: { 
    backgroundColor: '#dcfce7', 
    borderColor: '#16a34a' 
  },
  sideTabActiveSell: { 
    backgroundColor: '#fef2f2', 
    borderColor: '#dc2626' 
  },
  sideTabText: { 
    fontWeight: '700', 
    color: '#6b7280' 
  },
  sideTabTextActive: { 
    color: '#111827' 
  },
  typeRow: { 
    marginBottom: 16 
  },
  toggleWrap: {
    flexDirection: 'row',
    backgroundColor: '#f1f5f9',
    borderRadius: 12,
    padding: 4,
    gap: 4,
  },
  toggleBtn: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 8,
  },
  toggleBtnActive: { 
    backgroundColor: '#fff',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  toggleText: { 
    color: '#64748b', 
    fontWeight: '600',
    fontSize: 14,
  },
  toggleTextActive: { 
    color: '#1e293b', 
    fontWeight: '700' 
  },
  fieldLabel: { 
    color: '#6b7280', 
    marginBottom: 8,
    fontSize: 14,
    fontWeight: '500',
  },
  input: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 16,
    flex: 1,
  },
  priceRowInner: { 
    flexDirection: 'row', 
    alignItems: 'center', 
    gap: 8 
  },
  stepBtn: {
    width: 44,
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f8fafc',
  },
  inline: { 
    flexDirection: 'row', 
    alignItems: 'center' 
  },
  marketPrice: { 
    fontWeight: '600',
    fontSize: 16,
    color: '#6b7280',
  },
  qtyQuick: { 
    flexDirection: 'row', 
    gap: 8, 
    marginTop: 8 
  },
  qtyPill: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    backgroundColor: '#f8fafc',
  },
  qtyPillText: { 
    fontWeight: '600',
    fontSize: 14,
    color: '#374151',
  },
  summary: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 4,
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    marginVertical: 8,
  },
  summaryKey: { 
    color: '#6b7280',
    fontSize: 14,
    fontWeight: '500',
  },
  summaryVal: { 
    fontWeight: '700',
    fontSize: 16,
    color: '#111827',
  },
  submitBtn: {
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buyBtn: { 
    backgroundColor: '#16a34a' 
  },
  sellBtn: { 
    backgroundColor: '#dc2626' 
  },
  submitText: { 
    color: '#fff', 
    fontWeight: '800', 
    fontSize: 16 
  },
  autoBtn: {
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 8,
    backgroundColor: '#0ea5e9',
    flexDirection: 'row',
    gap: 8,
  },
  autoBtnActive: {
    backgroundColor: '#dc2626',
  },
  autoBtnText: { 
    color: '#fff', 
    fontWeight: '700', 
    fontSize: 16 
  },

  // 금액 입력 모달 스타일 추가
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
    width: '85%',
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 8,
    color: '#111827',
  },
  modalSubtitle: {
    fontSize: 14,
    color: '#6b7280',
    textAlign: 'center',
    marginBottom: 20,
  },
  modalInput: {
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 16,
    marginBottom: 16,
    textAlign: 'center',
    backgroundColor: '#fff',
  },
  quickAmountButtons: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 20,
  },
  quickAmountBtn: {
    flex: 1,
    minWidth: '45%',
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: '#f3f4f6',
    borderRadius: 8,
    alignItems: 'center',
  },
  quickAmountText: {
    fontSize: 12,
    color: '#374151',
    fontWeight: '500',
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
    backgroundColor: '#0ea5e9',
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
