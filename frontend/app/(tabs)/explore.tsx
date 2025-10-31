import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
  useColorScheme,
} from 'react-native';
import axios from 'axios';
import { useRouter } from 'expo-router';

const API_BASE = 'http://localhost:8000';

type Stock = {
  symbol: string;
  name: string;
  market: string;
};

export default function ExploreScreen() {
  const router = useRouter();
  const scheme = useColorScheme();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    
    if (query.length < 1) {
      setSearchResults([]);
      setSearched(false);
      return;
    }

    setLoading(true);
    setSearched(true);
    try {
      const response = await axios.get(`${API_BASE}/stocks/search`, {
        params: { q: query }
      });
      setSearchResults(response.data || []);
    } catch (error) {
      console.error('Search error:', error);
      setSearchResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectStock = (stock: Stock) => {
    router.push({
      pathname: '/trade/[symbol]',
      params: { symbol: stock.symbol, name: stock.name }
    });
  };

  const bg = scheme === 'dark' ? '#0b0f14' : '#fff';
  const inputBg = scheme === 'dark' ? '#1f2937' : '#f8fafc';
  const textColor = scheme === 'dark' ? '#fff' : '#111827';

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: bg }]}>
      <View style={styles.container}>
        <Text style={[styles.title, { color: textColor }]}>종목 검색</Text>
        
        <TextInput
          style={[styles.searchInput, { backgroundColor: inputBg, color: textColor }]}
          placeholder="종목명 또는 종목코드 입력 (예: 삼성전자, 005930)"
          placeholderTextColor={scheme === 'dark' ? '#9ca3af' : '#6b7280'}
          value={searchQuery}
          onChangeText={handleSearch}
          autoCapitalize="none"
          autoCorrect={false}
        />

        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#2563eb" />
            <Text style={[styles.loadingText, { color: textColor }]}>검색 중...</Text>
          </View>
        ) : (
          <FlatList
            data={searchResults}
            keyExtractor={(item) => item.symbol}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={styles.resultItem}
                onPress={() => handleSelectStock(item)}
                activeOpacity={0.7}
              >
                <View style={styles.resultLeft}>
                  <Text style={styles.resultSymbol}>{item.symbol}</Text>
                  <Text style={styles.resultName}>{item.name}</Text>
                </View>
                <View style={styles.resultRight}>
                  <View style={[
                    styles.marketBadge,
                    { backgroundColor: item.market === 'KOSPI' ? '#ecfdf5' : '#eff6ff' }
                  ]}>
                    <Text style={[
                      styles.marketText,
                      { color: item.market === 'KOSPI' ? '#16a34a' : '#2563eb' }
                    ]}>
                      {item.market}
                    </Text>
                  </View>
                </View>
              </TouchableOpacity>
            )}
            ItemSeparatorComponent={() => <View style={styles.separator} />}
            contentContainerStyle={styles.listContent}
            ListEmptyComponent={
              searched ? (
                <View style={styles.emptyContainer}>
                  <Text style={styles.emptyIcon}>🔍</Text>
                  <Text style={[styles.emptyText, { color: textColor }]}>
                    검색 결과가 없습니다
                  </Text>
                  <Text style={styles.emptyHint}>
                    종목명이나 종목코드를 정확히 입력해주세요
                  </Text>
                </View>
              ) : (
                <View style={styles.emptyContainer}>
                  <Text style={styles.emptyIcon}>💼</Text>
                  <Text style={[styles.emptyText, { color: textColor }]}>
                    종목을 검색하세요
                  </Text>
                  <Text style={styles.emptyHint}>
                    삼성전자, SK하이닉스, 005930 등
                  </Text>
                </View>
              )
            }
          />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: { flex: 1, padding: 16 },
  title: {
    fontSize: 28,
    fontWeight: '800',
    marginBottom: 16,
  },
  searchInput: {
    height: 50,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 12,
    paddingHorizontal: 16,
    fontSize: 16,
    marginBottom: 16,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    fontWeight: '600',
  },
  listContent: {
    paddingBottom: 24,
  },
  resultItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 16,
    paddingHorizontal: 12,
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  resultLeft: {
    flex: 1,
  },
  resultSymbol: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  resultName: {
    fontSize: 14,
    color: '#6b7280',
  },
  resultRight: {
    marginLeft: 12,
  },
  marketBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  marketText: {
    fontSize: 11,
    fontWeight: '700',
  },
  separator: {
    height: 8,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 80,
  },
  emptyIcon: {
    fontSize: 64,
    marginBottom: 16,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 8,
  },
  emptyHint: {
    fontSize: 14,
    color: '#9ca3af',
    textAlign: 'center',
  },
});
