import React, { useState } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, FlatList, ActivityIndicator } from 'react-native';
import { mobileClient } from '../api/client';

interface FileResult {
  path: string;
  name: string;
  size_bytes?: number;
  extension?: string;
}

export default function FileExplorerScreen() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<FileResult[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await mobileClient.searchFiles(query.trim());
      if (Array.isArray(res)) {
        setResults(res);
      } else if (res && Array.isArray(res.files)) {
        setResults(res.files);
      } else {
        setResults([]);
      }
    } catch (err) {
      console.log('File search notice:', err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.headerTitle}>DESKTOP FILE INDEXER & SEARCH</Text>

      <View style={styles.searchRow}>
        <TextInput
          style={styles.input}
          placeholder="Search desktop files (e.g., .py, pdf, config)..."
          placeholderTextColor="#557090"
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={handleSearch}
        />
        <TouchableOpacity style={styles.searchBtn} onPress={handleSearch} disabled={loading}>
          <Text style={styles.btnText}>SEARCH</Text>
        </TouchableOpacity>
      </View>

      {loading && <ActivityIndicator color="#00ff66" style={{ marginVertical: 12 }} />}

      <FlatList
        data={results}
        keyExtractor={(item, index) => item.path || `file_${index}`}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyText}>Enter a query to search indexed desktop files.</Text>
            </View>
          ) : null
        }
        renderItem={({ item }) => (
          <View style={styles.fileCard}>
            <Text style={styles.fileName}>📄 {item.name || item.path.split(/[\\/]/).pop()}</Text>
            <Text style={styles.filePath}>{item.path}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#050d08', padding: 16 },
  headerTitle: { color: '#00ff66', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 16 },
  searchRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  input: { flex: 1, backgroundColor: '#0a1a0f', color: '#ffffff', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.3)', fontFamily: 'monospace' },
  searchBtn: { backgroundColor: '#00cc52', paddingHorizontal: 16, borderRadius: 10, justifyContent: 'center' },
  btnText: { color: '#ffffff', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' },
  fileCard: { backgroundColor: '#0a1a0f', padding: 14, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)', marginBottom: 8 },
  fileName: { color: '#ffffff', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace' },
  filePath: { color: '#668877', fontSize: 10, marginTop: 4, fontFamily: 'monospace' },
  emptyBox: { padding: 30, alignItems: 'center' },
  emptyText: { color: '#557090', fontSize: 12, fontFamily: 'monospace', textAlign: 'center' }
});
