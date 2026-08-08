import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, FlatList, ActivityIndicator } from 'react-native';
import { mobileClient } from '../api/client';

interface ChatMessage {
  id: string;
  sender: 'user' | 'jarvis';
  text: string;
  timestamp: number;
}

export default function ChatScreen() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);

  const loadHistory = async () => {
    try {
      const data = await mobileClient.fetchChatHistory();
      if (data && Array.isArray(data.history)) {
        setMessages(data.history);
      }
    } catch (err) {
      console.log('Notice loading chat history:', err);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

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
      const res = await mobileClient.sendNaturalLanguageCommand(userMsgText);
      const jarvisMsg: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        sender: 'jarvis',
        text: res.response || res.message || 'Command executed, sir.',
        timestamp: Date.now()
      };
      setMessages((prev) => [...prev, jarvisMsg]);
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

  return (
    <View style={styles.container}>
      <Text style={styles.headerTitle}>J.A.R.V.I.S. MOBILE CHAT</Text>

      <FlatList
        data={messages}
        keyExtractor={(item) => item.id}
        style={styles.messageList}
        renderItem={({ item }) => (
          <View style={[styles.bubble, item.sender === 'user' ? styles.userBubble : styles.jarvisBubble]}>
            <Text style={styles.senderText}>{item.sender === 'user' ? 'YOU' : 'J.A.R.V.I.S.'}</Text>
            <Text style={styles.messageText}>{item.text}</Text>
          </View>
        )}
      />

      {loading && <ActivityIndicator color="#00ff66" style={{ marginVertical: 8 }} />}

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
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#050d08', padding: 16 },
  headerTitle: { color: '#00ff66', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 16 },
  messageList: { flex: 1, marginBottom: 12 },
  bubble: { padding: 12, borderRadius: 12, marginVertical: 6, maxWidth: '85%' },
  userBubble: { backgroundColor: '#0a2215', alignSelf: 'flex-end', borderWidth: 1, borderColor: '#00cc52' },
  jarvisBubble: { backgroundColor: '#0a1a0f', alignSelf: 'flex-start', borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)' },
  senderText: { color: '#00ff66', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 4 },
  messageText: { color: '#ffffff', fontSize: 13, fontFamily: 'monospace' },
  inputContainer: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  textInput: { flex: 1, backgroundColor: '#0a1a0f', color: '#ffffff', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.3)', fontFamily: 'monospace' },
  sendBtn: { backgroundColor: '#00cc52', paddingHorizontal: 16, paddingVertical: 12, borderRadius: 10, justifyContent: 'center' },
  sendBtnText: { color: '#ffffff', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' }
});
