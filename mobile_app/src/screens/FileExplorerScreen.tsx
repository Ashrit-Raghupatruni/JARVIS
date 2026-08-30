import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  Alert
} from 'react-native';
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

  const getExtensionBadge = (path: string) => {
    const ext = path.split('.').pop()?.toUpperCase() || 'FILE';
    return ext.slice(0, 4);
  };

  const formatSize = (bytes?: number) => {
    if (!bytes) return '';
    if (bytes > 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
    if (bytes > 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${bytes} B`;
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.headerBar}>
        <Text style={styles.headerTitle}>DESKTOP FILE INDEXER</Text>
        <Text style={styles.headerSubtitle}>FAST LOCAL SEMANTIC & FILENAME SEARCH</Text>
      </View>

      {/* Search Bar */}
      <View style={styles.searchRow}>
        <TextInput
          style={styles.input}
          placeholder="Search desktop files (.py, .ts, pdf, docs)..."
          placeholderTextColor="#475569"
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={handleSearch}
        />
        <TouchableOpacity style={styles.searchBtn} onPress={handleSearch} disabled={loading}>
          <Text style={styles.btnText}>SEARCH</Text>
        </TouchableOpacity>
      </View>

      {loading && (
        <View style={styles.loadingBox}>
          <ActivityIndicator color="#00e5ff" size="small" />
          <Text style={styles.loadingText}>Searching desktop index...</Text>
        </View>
      )}

      <FlatList
        data={results}
        keyExtractor={(item, index) => item.path || `file_${index}`}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyIcon}>📁</Text>
              <Text style={styles.emptyTitle}>Desktop Index Explorer</Text>
              <Text style={styles.emptySub}>
                Enter filename or extension query to locate files on your desktop workstation.
              </Text>
            </View>
          ) : null
        }
        renderItem={({ item }) => {
          const fileName = item.name || item.path.split(/[\\/]/).pop() || 'Unknown';
          const ext = getExtensionBadge(item.path);
          return (
            <TouchableOpacity
              style={styles.fileCard}
              onPress={() => Alert.alert("Desktop File Location", item.path)}
            >
              <View style={styles.fileHeader}>
                <View style={styles.extBadge}>
                  <Text style={styles.extBadgeText}>{ext}</Text>
                </View>
                <Text style={styles.fileName} numberOfLines={1}>{fileName}</Text>
                {item.size_bytes ? (
                  <Text style={styles.fileSize}>{formatSize(item.size_bytes)}</Text>
                ) : null}
              </View>
              <Text style={styles.filePath} numberOfLines={1}>{item.path}</Text>
            </TouchableOpacity>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#030712', padding: 16 },
  headerBar: { marginBottom: 14, borderBottomWidth: 1, borderBottomColor: '#1e293b', paddingBottom: 10 },
  headerTitle: { color: '#f8fafc', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1 },
  headerSubtitle: { color: '#64748b', fontSize: 9, fontFamily: 'monospace', marginTop: 2 },
  searchRow: { flexDirection: 'row', gap: 8, marginBottom: 14 },
  input: { flex: 1, backgroundColor: '#0b1329', color: '#f8fafc', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 11, borderWidth: 1, borderColor: '#334155', fontFamily: 'monospace', fontSize: 12 },
  searchBtn: { backgroundColor: '#00e5ff', paddingHorizontal: 16, borderRadius: 10, justifyContent: 'center' },
  btnText: { color: '#030712', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  loadingBox: { flexDirection: 'row', alignItems: 'center', gap: 8, marginVertical: 8, justifyContent: 'center' },
  loadingText: { color: '#64748b', fontSize: 11, fontFamily: 'monospace' },
  fileCard: { backgroundColor: '#0b1329', padding: 12, borderRadius: 12, borderWidth: 1, borderColor: '#1e293b', marginBottom: 8 },
  fileHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  extBadge: { backgroundColor: '#00e5ff20', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, borderWidth: 1, borderColor: '#00e5ff40' },
  extBadgeText: { color: '#00e5ff', fontSize: 8, fontWeight: 'bold', fontFamily: 'monospace' },
  fileName: { color: '#f8fafc', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace', flex: 1 },
  fileSize: { color: '#64748b', fontSize: 10, fontFamily: 'monospace' },
  filePath: { color: '#64748b', fontSize: 10, marginTop: 4, fontFamily: 'monospace' },
  emptyBox: { padding: 40, alignItems: 'center' },
  emptyIcon: { fontSize: 32, marginBottom: 8 },
  emptyTitle: { color: '#f8fafc', fontSize: 14, fontWeight: 'bold', fontFamily: 'monospace' },
  emptySub: { color: '#64748b', fontSize: 11, fontFamily: 'monospace', textAlign: 'center', marginTop: 6, lineHeight: 16 }
});

