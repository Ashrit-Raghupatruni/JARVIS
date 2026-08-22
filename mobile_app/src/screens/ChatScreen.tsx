import React, { useState, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  ScrollView
} from 'react-native';
import { mobileClient, ConversationListItem, ConversationDetail } from '../api/client';

interface ChatMessage {
  id: string;
  sender: 'user' | 'jarvis' | 'system';
  text: string;
  timestamp: number | string;
}

export default function ChatScreen() {
  const [viewMode, setViewMode] = useState<'sessions' | 'thread'>('sessions');
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [activeConvTitle, setActiveConvTitle] = useState<string>('New Conversation');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Load conversation sessions from backend desktop SQLite API
  const loadConversations = async () => {
    try {
      setRefreshing(true);
      const res = await mobileClient.fetchConversations(50);
      if (res && Array.isArray(res.conversations)) {
        setConversations(res.conversations);
      }
    } catch (err) {
      console.log('Notice loading conversations:', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadConversations();
  }, []);

  // Filter conversations by search query
  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase().trim();
    return conversations.filter(
      (c) =>
        (c.title && c.title.toLowerCase().includes(q)) ||
        (c.summary && c.summary.toLowerCase().includes(q))
    );
  }, [conversations, searchQuery]);

  // Open single conversation thread
  const openConversation = async (conv: ConversationListItem) => {
    setActiveConvId(conv.id);
    setActiveConvTitle(conv.title || `Conversation #${conv.id}`);
    setViewMode('thread');
    setLoading(true);

    try {
      const res = await mobileClient.fetchConversationById(conv.id);
      if (res && res.conversation && Array.isArray(res.conversation.messages)) {
        const mappedMsgs: ChatMessage[] = res.conversation.messages.map((m) => ({
          id: m.id || `m_${Math.random()}`,
          sender: m.role === 'user' ? 'user' : m.role === 'system' ? 'system' : 'jarvis',
          text: m.content,
          timestamp: m.timestamp
        }));
        setMessages(mappedMsgs);
      } else {
        setMessages([]);
      }
    } catch (err) {
      console.log('Error opening conversation:', err);
      setMessages([]);
    } finally {
      setLoading(false);
    }
  };

  // Start fresh thread
  const startNewConversation = () => {
    setActiveConvId(null);
    setActiveConvTitle('New Session');
    setMessages([]);
    setViewMode('thread');
  };

  // Send message in current thread
  const sendMessage = async () => {
    if (!inputText.trim()) return;

    const userMsgText = inputText.trim();
    const userMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      sender: 'user',
      text: userMsgText,
      timestamp: Date.now()
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setLoading(true);

    try {
      const res = await mobileClient.sendNaturalLanguageCommand(userMsgText, activeConvId);
      const jarvisReply = res.response || res.message || res.text || 'Command executed, sir.';
      const jarvisMsg: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        sender: 'jarvis',
        text: jarvisReply,
        timestamp: Date.now()
      };
      setMessages((prev) => [...prev, jarvisMsg]);

      // If this was a new conversation, refresh the list in background
      if (!activeConvId) {
        loadConversations();
      }
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: `msg_err_${Date.now()}`,
        sender: 'jarvis',
        text: `Error executing command: ${String(err)}`,
        timestamp: Date.now()
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  // Format relative timestamp
  const formatTime = (ts: string | number) => {
    try {
      const date = new Date(ts);
      if (isNaN(date.getTime())) return '';
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <View style={styles.container}>
      {/* ── Top Header Navigation Bar ── */}
      <View style={styles.headerBar}>
        {viewMode === 'thread' ? (
          <View style={styles.headerThreadRow}>
            <TouchableOpacity style={styles.backBtn} onPress={() => setViewMode('sessions')}>
              <Text style={styles.backBtnText}>← SESSIONS</Text>
            </TouchableOpacity>
            <Text style={styles.threadTitle} numberOfLines={1}>
              {activeConvTitle}
            </Text>
          </View>
        ) : (
          <View style={styles.headerListRow}>
            <Text style={styles.headerTitle}>💬 CONVERSATION HISTORY</Text>
            <TouchableOpacity style={styles.newChatBtn} onPress={startNewConversation}>
              <Text style={styles.newChatBtnText}>➕ NEW CHAT</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* ── Mode 1: SESSIONS / HISTORY BROWSER ── */}
      {viewMode === 'sessions' && (
        <View style={styles.contentFlex}>
          {/* Search Bar */}
          <View style={styles.searchContainer}>
            <Text style={styles.searchIcon}>🔍</Text>
            <TextInput
              style={styles.searchInput}
              placeholder="Search conversations by title or topic..."
              placeholderTextColor="#557090"
              value={searchQuery}
              onChangeText={setSearchQuery}
            />
            {searchQuery.length > 0 && (
              <TouchableOpacity onPress={() => setSearchQuery('')}>
                <Text style={styles.clearIcon}>✕</Text>
              </TouchableOpacity>
            )}
          </View>

          {/* Conversations List */}
          <FlatList
            data={filteredConversations}
            keyExtractor={(item) => String(item.id)}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={loadConversations} tintColor="#00ff66" />}
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyIcon}>📂</Text>
                <Text style={styles.emptyTitle}>
                  {searchQuery ? 'No matching conversations' : 'No past conversations'}
                </Text>
                <Text style={styles.emptySub}>
                  {searchQuery ? 'Try a different search term' : 'Start a chat session with JARVIS'}
                </Text>
              </View>
            }
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.convCard} onPress={() => openConversation(item)}>
                <View style={styles.convHeader}>
                  <Text style={styles.convTitle} numberOfLines={1}>
                    {item.title || `Session #${item.id}`}
                  </Text>
                  <View style={styles.msgCountBadge}>
                    <Text style={styles.msgCountText}>{item.message_count || 0} msgs</Text>
                  </View>
                </View>
                {item.summary && (
                  <Text style={styles.convSummary} numberOfLines={2}>
                    {item.summary}
                  </Text>
                )}
                <View style={styles.convFooter}>
                  <Text style={styles.convTime}>{formatTime(item.updated_at || item.created_at)}</Text>
                  <Text style={styles.convArrow}>Open →</Text>
                </View>
              </TouchableOpacity>
            )}
          />
        </View>
      )}

      {/* ── Mode 2: ACTIVE THREAD VIEWER ── */}
      {viewMode === 'thread' && (
        <View style={styles.contentFlex}>
          <FlatList
            data={messages}
            keyExtractor={(item) => item.id}
            style={styles.messageList}
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyIcon}>💬</Text>
                <Text style={styles.emptyTitle}>Ready for Commands</Text>
                <Text style={styles.emptySub}>Ask JARVIS or control desktop apps</Text>
              </View>
            }
            renderItem={({ item }) => (
              <View
                style={[
                  styles.bubble,
                  item.sender === 'user'
                    ? styles.userBubble
                    : item.sender === 'system'
                    ? styles.systemBubble
                    : styles.jarvisBubble
                ]}
              >
                <Text
                  style={[
                    styles.senderText,
                    item.sender === 'user'
                      ? styles.userSenderText
                      : item.sender === 'system'
                      ? styles.systemSenderText
                      : styles.jarvisSenderText
                  ]}
                >
                  {item.sender === 'user' ? 'YOU' : item.sender === 'system' ? 'SYSTEM' : 'J.A.R.V.I.S.'}
                </Text>
                <Text style={styles.messageText}>{item.text}</Text>
              </View>
            )}
          />

          {loading && <ActivityIndicator color="#00ff66" style={{ marginVertical: 8 }} />}

          {/* Chat Input */}
          <View style={styles.inputContainer}>
            <TextInput
              style={styles.textInput}
              placeholder="Ask JARVIS or send desktop command..."
              placeholderTextColor="#557090"
              value={inputText}
              onChangeText={setInputText}
              onSubmitEditing={sendMessage}
            />
            <TouchableOpacity style={styles.sendBtn} onPress={sendMessage} disabled={loading}>
              <Text style={styles.sendBtnText}>SEND</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#050d08', padding: 16 },
  contentFlex: { flex: 1 },
  headerBar: { marginBottom: 12, borderBottomWidth: 1, borderBottomColor: 'rgba(0, 255, 102, 0.15)', paddingBottom: 10 },
  headerListRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  headerTitle: { color: '#00ff66', fontSize: 15, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1 },
  newChatBtn: { backgroundColor: 'rgba(0, 255, 102, 0.15)', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: '#00ff66' },
  newChatBtnText: { color: '#00ff66', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  headerThreadRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  backBtn: { backgroundColor: '#0a1a0f', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.3)' },
  backBtnText: { color: '#00ff66', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  threadTitle: { color: '#ffffff', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace', flex: 1 },
  searchContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0a1a0f', borderRadius: 10, paddingHorizontal: 12, marginBottom: 12, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)' },
  searchIcon: { fontSize: 14, marginRight: 8 },
  searchInput: { flex: 1, color: '#ffffff', paddingVertical: 10, fontFamily: 'monospace', fontSize: 12 },
  clearIcon: { color: '#557090', fontSize: 14, padding: 4 },
  convCard: { backgroundColor: '#0a1a0f', padding: 14, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.15)', marginBottom: 10 },
  convHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  convTitle: { color: '#ffffff', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace', flex: 1, marginRight: 8 },
  msgCountBadge: { backgroundColor: 'rgba(0, 255, 102, 0.1)', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.3)' },
  msgCountText: { color: '#00ff66', fontSize: 10, fontFamily: 'monospace' },
  convSummary: { color: '#88aa99', fontSize: 11, fontFamily: 'monospace', marginBottom: 8 },
  convFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderTopWidth: 1, borderTopColor: 'rgba(0, 255, 102, 0.08)', paddingTop: 6 },
  convTime: { color: '#557090', fontSize: 10, fontFamily: 'monospace' },
  convArrow: { color: '#00cc52', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  emptyContainer: { alignItems: 'center', justifyContent: 'center', paddingVertical: 40 },
  emptyIcon: { fontSize: 32, marginBottom: 8 },
  emptyTitle: { color: '#ffffff', fontSize: 14, fontWeight: 'bold', fontFamily: 'monospace' },
  emptySub: { color: '#557090', fontSize: 11, fontFamily: 'monospace', marginTop: 4 },
  messageList: { flex: 1, marginBottom: 12 },
  bubble: { padding: 12, borderRadius: 12, marginVertical: 6, maxWidth: '85%' },
  userBubble: { backgroundColor: '#0a2215', alignSelf: 'flex-end', borderWidth: 1, borderColor: '#00cc52' },
  jarvisBubble: { backgroundColor: '#0a1a0f', alignSelf: 'flex-start', borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)' },
  systemBubble: { backgroundColor: '#151520', alignSelf: 'center', borderWidth: 1, borderColor: 'rgba(100, 150, 255, 0.3)' },
  senderText: { fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 4 },
  userSenderText: { color: '#00ff66' },
  jarvisSenderText: { color: '#00e5ff' },
  systemSenderText: { color: '#88aaff' },
  messageText: { color: '#ffffff', fontSize: 13, fontFamily: 'monospace', lineHeight: 18 },
  inputContainer: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  textInput: { flex: 1, backgroundColor: '#0a1a0f', color: '#ffffff', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.3)', fontFamily: 'monospace', fontSize: 12 },
  sendBtn: { backgroundColor: '#00cc52', paddingHorizontal: 16, paddingVertical: 12, borderRadius: 10, justifyContent: 'center' },
  sendBtnText: { color: '#ffffff', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' }
});
