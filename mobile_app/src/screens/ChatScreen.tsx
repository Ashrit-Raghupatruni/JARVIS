import React, { useState, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  RefreshControl
} from 'react-native';
import { mobileClient, ConversationListItem } from '../api/client';

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

  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations;
    const q = searchQuery.toLowerCase().trim();
    return conversations.filter(
      (c) =>
        (c.title && c.title.toLowerCase().includes(q)) ||
        (c.summary && c.summary.toLowerCase().includes(q))
    );
  }, [conversations, searchQuery]);

  const openConversation = async (conv: ConversationListItem) => {
    setActiveConvId(conv.id);
    setActiveConvTitle(conv.title || `Session #${conv.id}`);
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

  const startNewConversation = () => {
    setActiveConvId(null);
    setActiveConvTitle('New Session');
    setMessages([]);
    setViewMode('thread');
  };

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
      const jarvisReply = res.response || res.message || res.text || 'Command acknowledged and executed.';
      const jarvisMsg: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        sender: 'jarvis',
        text: jarvisReply,
        timestamp: Date.now()
      };
      setMessages((prev) => [...prev, jarvisMsg]);

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
      {/* Top Header */}
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
            <View>
              <Text style={styles.headerTitle}>MISSION CHAT THREADS</Text>
              <Text style={styles.headerSubtitle}>MULTI-TURN CONVERSATIONS WITH JARVIS</Text>
            </View>
            <TouchableOpacity style={styles.newChatBtn} onPress={startNewConversation}>
              <Text style={styles.newChatBtnText}>+ NEW</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* Mode 1: Sessions List */}
      {viewMode === 'sessions' && (
        <View style={styles.contentFlex}>
          <View style={styles.searchContainer}>
            <TextInput
              style={styles.searchInput}
              placeholder="Search conversations by title or topic..."
              placeholderTextColor="#475569"
              value={searchQuery}
              onChangeText={setSearchQuery}
            />
            {searchQuery.length > 0 && (
              <TouchableOpacity onPress={() => setSearchQuery('')}>
                <Text style={styles.clearIcon}>✕</Text>
              </TouchableOpacity>
            )}
          </View>

          <FlatList
            data={filteredConversations}
            keyExtractor={(item) => String(item.id)}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={loadConversations} tintColor="#00e5ff" />}
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyIcon}>📂</Text>
                <Text style={styles.emptyTitle}>
                  {searchQuery ? 'No matching conversations' : 'No past sessions recorded'}
                </Text>
                <Text style={styles.emptySub}>
                  {searchQuery ? 'Try a different search term' : 'Start a new conversation thread with JARVIS'}
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
                    <Text style={styles.msgCountText}>{item.message_count || 0} MSGS</Text>
                  </View>
                </View>
                {item.summary && (
                  <Text style={styles.convSummary} numberOfLines={2}>
                    {item.summary}
                  </Text>
                )}
                <View style={styles.convFooter}>
                  <Text style={styles.convTime}>{formatTime(item.updated_at || item.created_at)}</Text>
                  <Text style={styles.convArrow}>RESUME →</Text>
                </View>
              </TouchableOpacity>
            )}
          />
        </View>
      )}

      {/* Mode 2: Active Thread Viewer */}
      {viewMode === 'thread' && (
        <View style={styles.contentFlex}>
          <FlatList
            data={messages}
            keyExtractor={(item) => item.id}
            style={styles.messageList}
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyIcon}>💬</Text>
                <Text style={styles.emptyTitle}>Direct Assistant Channel</Text>
                <Text style={styles.emptySub}>Send a query, command, or workflow plan to execute.</Text>
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
                  {item.sender === 'user' ? 'OPERATOR' : item.sender === 'system' ? 'SYSTEM' : 'JARVIS CORE'}
                </Text>
                <Text style={styles.messageText}>{item.text}</Text>
              </View>
            )}
          />

          {loading && (
            <View style={styles.thinkingBox}>
              <ActivityIndicator color="#00e5ff" size="small" />
              <Text style={styles.thinkingText}>JARVIS is generating response...</Text>
            </View>
          )}

          {/* Chat Input Bar */}
          <View style={styles.inputContainer}>
            <TextInput
              style={styles.textInput}
              placeholder="Ask JARVIS or dispatch desktop command..."
              placeholderTextColor="#475569"
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
  container: { flex: 1, backgroundColor: '#030712', padding: 16 },
  contentFlex: { flex: 1 },
  headerBar: { marginBottom: 12, borderBottomWidth: 1, borderBottomColor: '#1e293b', paddingBottom: 10 },
  headerListRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  headerTitle: { color: '#f8fafc', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1 },
  headerSubtitle: { color: '#64748b', fontSize: 9, fontFamily: 'monospace', marginTop: 2 },
  newChatBtn: { backgroundColor: '#00e5ff', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 },
  newChatBtnText: { color: '#030712', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  headerThreadRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  backBtn: { backgroundColor: '#0b1329', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: '#334155' },
  backBtnText: { color: '#00e5ff', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  threadTitle: { color: '#f8fafc', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace', flex: 1 },
  
  searchContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0b1329', borderRadius: 10, paddingHorizontal: 12, marginBottom: 12, borderWidth: 1, borderColor: '#1e293b' },
  searchInput: { flex: 1, color: '#f8fafc', paddingVertical: 10, fontFamily: 'monospace', fontSize: 12 },
  clearIcon: { color: '#64748b', fontSize: 14, padding: 4 },

  convCard: { backgroundColor: '#0b1329', padding: 14, borderRadius: 12, borderWidth: 1, borderColor: '#1e293b', marginBottom: 10 },
  convHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  convTitle: { color: '#f8fafc', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace', flex: 1, marginRight: 8 },
  msgCountBadge: { backgroundColor: '#030712', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, borderWidth: 1, borderColor: '#334155' },
  msgCountText: { color: '#00e5ff', fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace' },
  convSummary: { color: '#94a3b8', fontSize: 11, fontFamily: 'monospace', marginBottom: 8, lineHeight: 16 },
  convFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderTopWidth: 1, borderTopColor: '#1e293b', paddingTop: 8 },
  convTime: { color: '#64748b', fontSize: 9, fontFamily: 'monospace' },
  convArrow: { color: '#00e5ff', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },

  emptyContainer: { alignItems: 'center', justifyContent: 'center', paddingVertical: 50 },
  emptyIcon: { fontSize: 32, marginBottom: 8 },
  emptyTitle: { color: '#f8fafc', fontSize: 14, fontWeight: 'bold', fontFamily: 'monospace' },
  emptySub: { color: '#64748b', fontSize: 11, fontFamily: 'monospace', marginTop: 4 },

  messageList: { flex: 1, marginBottom: 12 },
  bubble: { padding: 12, borderRadius: 14, marginVertical: 6, maxWidth: '85%' },
  userBubble: { backgroundColor: '#0b192e', alignSelf: 'flex-end', borderWidth: 1, borderColor: '#00e5ff50' },
  jarvisBubble: { backgroundColor: '#0b1329', alignSelf: 'flex-start', borderWidth: 1, borderColor: '#1e293b' },
  systemBubble: { backgroundColor: '#180d2b', alignSelf: 'center', borderWidth: 1, borderColor: '#a855f750' },
  senderText: { fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 4 },
  userSenderText: { color: '#00e5ff' },
  jarvisSenderText: { color: '#10b981' },
  systemSenderText: { color: '#c084fc' },
  messageText: { color: '#f8fafc', fontSize: 13, fontFamily: 'monospace', lineHeight: 18 },

  thinkingBox: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 },
  thinkingText: { color: '#64748b', fontSize: 11, fontFamily: 'monospace' },

  inputContainer: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  textInput: { flex: 1, backgroundColor: '#0b1329', color: '#f8fafc', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#334155', fontFamily: 'monospace', fontSize: 12 },
  sendBtn: { backgroundColor: '#00e5ff', paddingHorizontal: 16, paddingVertical: 12, borderRadius: 10, justifyContent: 'center' },
  sendBtnText: { color: '#030712', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' }
});

