// Chart.tsx 파일
import * as haptics from 'expo-haptics';
import { useState } from 'react';
import { LayoutChangeEvent, StyleSheet, Text, View } from 'react-native';
import { CandlestickChart } from 'react-native-wagmi-charts';
import type { ChartProps } from '../lib/api/types';

function invokeHaptic() {
  haptics.impactAsync(haptics.ImpactFeedbackStyle.Light);
}

const Chart = ({ data }: ChartProps) => {
  const [parentWidth, setParentWidth] = useState<number>(0);

  const handleLayout = (event: LayoutChangeEvent) => {
    setParentWidth(event.nativeEvent.layout.width);
  };

  const formatDate = (value: number) => new Date(value).toISOString().slice(0, 10);

  // 여기가 위에서 보여준 return 부분입니다
  return (
    <View style={styles.container} onLayout={handleLayout}>
      {data.length > 0 && parentWidth > 0 ? (
        <CandlestickChart.Provider data={data}>
          <CandlestickChart
            height={200}
            width={parentWidth - 32}
          >
            <CandlestickChart.Candles
              positiveColor="#dc2626"    // 빨간색 (상승)
              negativeColor="#16a34a"    // 초록색 (하락)
            />
            // ... 나머지 코드
          </CandlestickChart>
        </CandlestickChart.Provider>
      ) : (
        <View style={styles.placeholder}>
          <Text>차트 로딩 중...</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  // 스타일 정의들...
});

export default Chart;
