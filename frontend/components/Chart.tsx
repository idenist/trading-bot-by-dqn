import * as haptics from 'expo-haptics';
import { useState } from 'react';
import { LayoutChangeEvent, StyleSheet, Text, View } from 'react-native';
import { CandlestickChart } from 'react-native-wagmi-charts';
import type { ChartProps } from '../lib/api/types';
function invokeHaptic() {
  haptics.impactAsync(haptics.ImpactFeedbackStyle.Light);
}
// Define the data for the candlestick chart
// The data must be an array of objects with the specified keys:
// timestamp, open, high, low, and close.

const Chart = ({ data }: ChartProps) => {
  const [parentWidth, setParentWidth] = useState<number>(0);

  const handleLayout = (event: LayoutChangeEvent) => {
    setParentWidth(event.nativeEvent.layout.width);
    // console.log('Measured Width:', event.nativeEvent.layout.width);
  };
  console.log('Parent Width:', parentWidth);
  console.log('Dummy Data Length:', data.length);
  const formatDate = (value: number) => new Date(value).toISOString().slice(0, 10);
  return (
    <View style={styles.container} onLayout={handleLayout}>
      {data.length > 0 && parentWidth > 0 ? (
        <CandlestickChart.Provider data={data}>
          <CandlestickChart
            height={200}
            width={parentWidth - 32}
          >
            <CandlestickChart.Candles />
            <CandlestickChart.Crosshair onCurrentXChange={invokeHaptic}>
              <CandlestickChart.Tooltip style={styles.tooltip}>
                <CandlestickChart.PriceText
                  type="close"
                  precision={0}
                  style={styles.tooltipPriceText}
                />
              </CandlestickChart.Tooltip>
            </CandlestickChart.Crosshair>
          </CandlestickChart>
          <View style={{maxWidth: parentWidth-32,flexDirection: 'row', flexWrap: "wrap",justifyContent: 'flex-start', marginTop: 8}}>
            <CandlestickChart.PriceText
              type="open"
              precision={0}
              style={styles.labelText}
              format={({value}) => `시가: ${value}`}
            />
            <CandlestickChart.PriceText
              type="high"
              precision={0}
              style={styles.labelText}
              format={({value}) => `고가: ${value}`}
            />
            <CandlestickChart.PriceText
              type="low"
              precision={0}
              style={styles.labelText}
              format={({value}) => `저가: ${value}`}
            />
            <CandlestickChart.PriceText
              type="close"
              precision={0}
              style={styles.labelText}
              format={({value}) => `종가: ${value}`}
            />
            <CandlestickChart.DatetimeText
              format={({value}) => {'worklet'; const formatted = formatDate(value); return formatted;}}
              style={styles.labelText}
            />
          </View>
        </CandlestickChart.Provider>
      ) : (
        // 레이아웃 측정 전이나 데이터가 없을 때 표시할 대체 뷰
        <View style={styles.placeholder}>
          <Text>차트 로딩 중...</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  placeholder: {
    flex: 1, 
    justifyContent: 'center', 
    alignItems: 'center'
  },
  container: {
    padding: 16,
    backgroundColor: '#f8f8f8',
    borderRadius: 8,
    height: 'auto',
  },
  chartTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2d2d2dff',
    marginBottom: 10,
    textAlign: 'center',
  },
  priceText: {
    color: '#000',
    fontSize: 16,
    fontWeight: 'bold',
  },
  tooltipPriceText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  datetimeText: {
    minWidth: 0,
    width: 80,
    color: '#ccc',
    fontSize: 12,
  },
  labelText: {
    minWidth: 0,
    width: 80,
    color: '#555',
    fontSize: 12,
    marginBottom: 4,
  },
  tooltip: {
    padding: 4,
    minWidth: 0,
    width: 80,
    maxWidth: 120,
    borderRadius: 4,
    backgroundColor: '#262626', // 필요시
  }
});

export default Chart;