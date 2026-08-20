import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, Alert, ScrollView, Switch } from 'react-native';
import { mobileClient } from '../api/client';

export default function ControlScreen() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [isLiveMode, setIsLiveMode] = useState(false);
  const [liveStatusMsg, setLiveStatusMsg] = useState('Standing By');
  const [isListening, setIsListening] = useState(false);

  const fetchLiveStatus = async () => {
    try {
      const status = await mobileClient.fetchLiveModeStatus();
      if (status.status === 'active' && status.frame) {
        setIsLiveMode(true);
        setLiveStatusMsg(`Active in ${status.frame.window_title || status.frame.active_app}`);
      } else {
        setIsLiveMode(false);
        setLiveStatusMsg('Standing By');
      }
    } catch (err) {
      console.log('Live mode status fetch notice:', err);
    }
  };

  useEffect(() => {
    fetchLiveStatus();
    const interval = setInterval(fetchLiveStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleLiveMode = async (value: boolean) => {
    try {
      const res = await mobileClient.toggleLiveMode(value);
      setIsLiveMode(res.live_mode_enabled);
      fetchLiveStatus();
    } catch (err) {
      Alert.alert('Live Mode Error', String(err));
    }
  };

  const sendCommandPrompt = async (commandText: string) => {
    const textToSend = commandText || prompt;
    if (!textToSend.trim()) {
      Alert.alert('Empty Prompt', 'Please enter a natural language command.');
      return;
    }

    setLoading(true);
    try {
      const res = await mobileClient.sendNaturalLanguageCommand(textToSend);
      Alert.alert('JARVIS Response', res.response || JSON.stringify(res));
      setPrompt('');
    } catch (err) {
      Alert.alert('Execution Error', String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleVoiceButtonPress = async () => {
    if (isListening) {
      // User tapped to stop recording -> finalize and send
      setIsListening(false);
      setLoading(true);
      try {
        // If voice text prompt was populated, send command
        if (prompt.trim()) {
          await sendCommandPrompt(prompt);
        } else {
          Alert.alert("🎙️ Microphone", "Audio frame captured and dispatched to desktop STT pipeline.");
        }
      } finally {
        setLoading(false);
      }
    } else {
      // User tapped to start listening
      setIsListening(true);
      // Connect WebSocket if not active and notify user
      mobileClient.connectWebSocket(
        () => {},
        (msg) => {
          if (msg.type === "voice_transcript" && msg.text) {
            setPrompt(msg.text);
            setIsListening(false);
          } else if (msg.type === "chat_response" && msg.text) {
            Alert.alert("JARVIS Response", msg.text);
            setIsListening(false);
          }
        }
      );
    }
  };

  const triggerCommand = async (cmd: string, params = {}) => {
    try {
      const res = await mobileClient.sendRemoteCommand(cmd, params);
      Alert.alert("Command Dispatched", JSON.stringify(res));
    } catch (err) {
      Alert.alert("Execution Failed", String(err));
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.headerTitle}>J.A.R.V.I.S. MOBILE CONTROL CENTER</Text>

      {/* ── LIVE MODE CONTROLLER ── */}
      <View style={styles.sectionCard}>
        <View style={styles.rowBetween}>
          <View>
            <Text style={styles.cardTitle}>👁️ LIVE MODE CO-PILOT</Text>
            <Text style={styles.cardSub}>{liveStatusMsg}</Text>
          </View>
          <Switch
            trackColor={{ false: '#122017', true: 'rgba(0, 255, 102, 0.4)' }}
            thumbColor={isLiveMode ? '#00ff66' : '#557090'}
            onValueChange={handleToggleLiveMode}
            value={isLiveMode}
          />
        </View>
      </View>

      {/* ── NATURAL LANGUAGE & VOICE COMMAND INPUT ── */}
      <View style={styles.sectionCard}>
        <Text style={styles.cardTitle}>💬 NATURAL LANGUAGE COMMAND</Text>
        <Text style={styles.cardSub}>Route prompts directly to Desktop Planner & Prash LLM</Text>

        <TextInput
          style={styles.textInput}
          placeholder="e.g. Open VS Code and check system diagnostics..."
          placeholderTextColor="#557090"
          value={prompt}
          onChangeText={setPrompt}
          multiline
        />

        <View style={styles.rowGap}>
          <TouchableOpacity
            style={[styles.actionBtn, styles.primaryBtn]}
            onPress={() => sendCommandPrompt(prompt)}
            disabled={loading}
          >
            <Text style={styles.btnText}>{loading ? 'SENDING...' : '⚡ SEND COMMAND'}</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.actionBtn, styles.voiceBtn, isListening && styles.listening]}
            onPress={handleVoiceButtonPress}
          >
            <Text style={styles.btnText}>{isListening ? '🎙️ LISTENING...' : '🎙️ VOICE'}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* ── QUICK REMOTE SYSTEM COMMANDS ── */}
      <View style={styles.sectionCard}>
        <Text style={styles.cardTitle}>🖥️ QUICK REMOTE COMMANDS</Text>
        <View style={styles.grid}>
          <TouchableOpacity style={[styles.cmdCard, styles.danger]} onPress={() => triggerCommand('shutdown')}>
            <Text style={styles.cmdTitle}>SHUTDOWN PC</Text>
            <Text style={styles.cmdSub}>Approval Gate</Text>
          </TouchableOpacity>

          <TouchableOpacity style={[styles.cmdCard, styles.warning]} onPress={() => triggerCommand('restart')}>
            <Text style={styles.cmdTitle}>RESTART PC</Text>
            <Text style={styles.cmdSub}>Approval Gate</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.cmdCard} onPress={() => triggerCommand('lock')}>
            <Text style={styles.cmdTitle}>LOCK PC</Text>
            <Text style={styles.cmdSub}>Instant Workstation</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.cmdCard} onPress={() => triggerCommand('open_app', { app_name: 'code' })}>
            <Text style={styles.cmdTitle}>LAUNCH VS CODE</Text>
            <Text style={styles.cmdSub}>IDE Workspace</Text>
          </TouchableOpacity>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#050d08', padding: 16 },
  headerTitle: { color: '#00ff66', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 16 },
  sectionCard: { backgroundColor: '#0a1a0f', padding: 16, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)', marginBottom: 16 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardTitle: { color: '#ffffff', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace' },
  cardSub: { color: '#00ff66', fontSize: 11, marginTop: 4, fontFamily: 'monospace' },
  textInput: { backgroundColor: '#050d08', color: '#ffffff', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.3)', minHeight: 60, marginVertical: 12, fontFamily: 'monospace' },
  rowGap: { flexDirection: 'row', gap: 10 },
  actionBtn: { flex: 1, padding: 12, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  primaryBtn: { backgroundColor: '#00cc52' },
  voiceBtn: { backgroundColor: 'rgba(0, 255, 102, 0.15)', borderWidth: 1, borderColor: '#00ff66' },
  listening: { backgroundColor: 'rgba(255, 0, 85, 0.3)', borderColor: '#ff0055' },
  btnText: { color: '#ffffff', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 12 },
  cmdCard: { width: '48%', backgroundColor: '#050d08', padding: 14, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)' },
  danger: { borderColor: '#ff0055' },
  warning: { borderColor: '#ff9900' },
  cmdTitle: { color: '#ffffff', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' },
  cmdSub: { color: '#668877', fontSize: 10, marginTop: 4 }
});
