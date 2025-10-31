import { useState, useEffect } from 'react';
import { Alert } from 'react-native';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export function useAutoTrade(symbol: string) {
  const [autoTradeActive, setAutoTradeActive] = useState(false);
  const [autoTradeLoading, setAutoTradeLoading] = useState(false);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await axios.get(`${API_BASE}/auto-trade/status`);
        const isRunning = response.data.running;
        const stocks = response.data.stocks || [];
        const newActive = isRunning && stocks.includes(symbol);
        
        if (newActive !== autoTradeActive) {
          console.log(`Auto trade status changed: ${autoTradeActive} -> ${newActive}`);
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

  const handleAutoTrade = async (sym: string) => {
    console.log(`Auto trade button clicked for ${sym}, current active: ${autoTradeActive}`);
    
    if (autoTradeActive) {
      Alert.alert('자동매매 중지', '정말 중지하시겠습니까?', [
        { text: '취소', style: 'cancel' },
        {
          text: '중지',
          onPress: async () => {
            setAutoTradeLoading(true);
            try {
              const response = await axios.post(`${API_BASE}/auto-trade/stop`);
              console.log('Stop response:', response.data);
              setAutoTradeActive(false);
              Alert.alert('성공', '자동매매가 중지되었습니다.');
            } catch (error: any) {
              console.error('Auto trade stop error:', error);
              Alert.alert('오류', '중지 실패');
            } finally {
              setAutoTradeLoading(false);
            }
          },
        },
      ]);
      return;
    }

    Alert.alert(
      '자동매매 시작',
      `${sym} 종목으로 자동매매를 시작하시겠습니까?\n\n※ DQN 서버가 실행 중이어야 합니다.`,
      [
        { text: '취소', style: 'cancel' },
        {
          text: '시작',
          onPress: async () => {
            setAutoTradeLoading(true);
            try {
              console.log(`Starting auto trade for ${sym}...`);
              
              const response = await axios.post(
                `${API_BASE}/auto-trade/start`,
                [sym],
                {
                  headers: { 'Content-Type': 'application/json' },
                  timeout: 10000
                }
              );
              
              console.log('Start response:', response.data);
              
              if (response.data.success) {
                setAutoTradeActive(true);
                Alert.alert('성공', `자동매매가 시작되었습니다.\n\n${response.data.message}`);
              } else {
                Alert.alert('실패', response.data.message || '시작 실패');
              }
            } catch (error: any) {
              console.error('Auto trade start error:', error);
              Alert.alert('오류', 'DQN 서버 연결 실패');
            } finally {
              setAutoTradeLoading(false);
            }
          },
        },
      ]
    );
  };

  return {
    autoTradeActive,
    autoTradeLoading,
    handleAutoTrade
  };
}
