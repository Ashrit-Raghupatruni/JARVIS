import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Alert,
  ScrollView,
  Switch,
  ActivityIndicator
} from 'react-native';
import { mobileClient } from '../api/client';

const QUICK_PROMPTS = [
  "Check system diagnostics",
  "Lock workstation",
  "Take screen capture",
  "Scan & resume goals",
  "Open VS Code",
  "List active windows"
];

export default function ControlScreen() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [isLiveMode, setIsLiveMode] = useState(false);
  const [liveStatusMsg, setLiveStatusMsg] = useState('Standing By');
  const [isListening, setIsListening] = useState(false);
  const [lastActionStatus, setLastActionStatus] = useState<string | null>(null);

  const fetchLiveStatus = async () => {
    try {
      const status = await mobileClient.fetchLiveModeStatus();
      if (status.status === 'active' && status.frame) {
        setIsLiveMode(true);
        setLiveStatusMsg(`Active in ${status.frame.window_title || status.frame.active_app}`);
      } else {
        setIsLiveMode(false);
        setLiveStatusMsg('Autonomous Co-Pilot Standby');
      }
    } catch (err) {
      // Background poll
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
      setIsLiveMode(Boolean(res.live_mode_enabled));
      fetchLiveStatus();
      setLastActionStatus(`Live Mode ${value ? 'ACTIVATED' : 'DEACTIVATED'}`);
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
      const reply = res.response || res.message || JSON.stringify(res);
      setLastActionStatus(`Dispatched: "${textToSend.slice(0, 32)}..."`);
      Alert.alert('JARVIS Response', reply);
      setPrompt('');
    } catch (err) {
      Alert.alert('Execution Error', String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleVoiceButtonPress = async () => {
    if (isListening) {
      setIsListening(false);
      setLoading(true);
      try {
        if (prompt.trim()) {
          await sendCommandPrompt(prompt);
        } else {
          Alert.alert("🎙️ Microphone", "Audio frame captured and dispatched to desktop STT pipeline.");
        }
      } finally {
        setLoading(false);
      }
    } else {
      setIsListening(true);
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

  const triggerCommand = async (cmd: string, params: Record<string, any> = {}) => {
    try {
      const res = await mobileClient.sendRemoteCommand(cmd, params);
      setLastActionStatus(`Executed ${cmd.toUpperCase()}`);
      Alert.alert("Command Executed", res.message || JSON.stringify(res));
    } catch (err) {
      Alert.alert("Execution Failed", String(err));
    }
  };

  const handleRecoverGoals = async () => {
    try {
      setLoading(true);
      const res = await mobileClient.recoverInterruptedGoals();
      if (res.status === 'success') {
        Alert.alert("Goal Recovery", `✓ Recovered ${res.recovered_count || 0} interrupted goal checkpoints.`);
        setLastActionStatus(`Recovered ${res.recovered_count || 0} goals`);
      } else {
        Alert.alert("Goal Recovery", res.message || "No interrupted goals found.");
      }
    } catch (e) {
      Alert.alert("Recovery Error", String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Header */}
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.headerTitle}>ACTION CONTROL CENTER</Text>
          <Text style={styles.headerSubtitle}>TACTICAL DESKTOP COMMAND & EXECUTIVE CONTROL</Text>
        </View>
        {lastActionStatus && (
          <View style={styles.lastActionBadge}>
            <Text style={styles.lastActionText}>{lastActionStatus}</Text>
          </View>
        )}
      </View>

      {/* Autonomous Live Mode Switch Card */}
      <View style={styles.liveCard}>
        <View style={styles.rowBetween}>
          <View style={{ flex: 1 }}>
            <View style={styles.liveBadgeRow}>
              <View style={[styles.statusDot, isLiveMode ? styles.dotActive : styles.dotStandby]} />
              <Text style={styles.liveTitle}>AUTONOMOUS LIVE VISION CO-PILOT</Text>
            </View>
            <Text style={styles.liveSubtitle}>{liveStatusMsg}</Text>
          </View>
          <Switch
            trackColor={{ false: '#1e293b', true: '#00e5ff50' }}
            thumbColor={isLiveMode ? '#00e5ff' : '#64748b'}
            onValueChange={handleToggleLiveMode}
            value={isLiveMode}
          />
        </View>
      </View>

      {/* Natural Language Prompt & Voice Command Hub */}
      <View style={styles.promptCard}>
        <Text style={styles.sectionLabel}>NATURAL LANGUAGE COMMAND</Text>
        
        <TextInput
          style={styles.textInput}
          placeholder="Enter command (e.g. Schedule meeting tomorrow at 3pm)..."
          placeholderTextColor="#475569"
          value={prompt}
          onChangeText={setPrompt}
          multiline
        />

        {/* Quick Suggestion Chips */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipsScroll}>
          {QUICK_PROMPTS.map((chip, idx) => (
            <TouchableOpacity
              key={idx}
              style={styles.chip}
              onPress={() => sendCommandPrompt(chip)}
            >
              <Text style={styles.chipText}>{chip}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        <View style={styles.actionButtonRow}>
          <TouchableOpacity
            style={[styles.primarySendBtn, loading && styles.disabledBtn]}
            onPress={() => sendCommandPrompt(prompt)}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#030712" size="small" />
            ) : (
              <Text style={styles.primarySendText}>⚡ EXECUTE PLAN</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.voiceMicBtn, isListening && styles.voiceListeningBtn]}
            onPress={handleVoiceButtonPress}
          >
            <Text style={styles.voiceMicIcon}>🎙️</Text>
            <Text style={styles.voiceMicText}>{isListening ? 'STREAMING...' : 'VOICE'}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Primary Workstation Quick Matrix */}
      <View style={styles.matrixCard}>
        <Text style={styles.sectionLabel}>WORKSTATION CONTROL MATRIX</Text>
        
        <View style={styles.grid}>
          <TouchableOpacity
            style={styles.gridCard}
            onPress={() => triggerCommand('lock')}
          >
            <Text style={styles.gridIcon}>🔒</Text>
            <Text style={styles.gridTitle}>LOCK WORKSTATION</Text>
            <Text style={styles.gridSub}>Instant Win32 Lock</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.gridCard}
            onPress={() => triggerCommand('take_screenshot')}
          >
            <Text style={styles.gridIcon}>📸</Text>
            <Text style={styles.gridTitle}>SCREEN CAPTURE</Text>
            <Text style={styles.gridSub}>Desktop Snapshot</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.gridCard}
            onPress={() => triggerCommand('open_terminal')}
          >
            <Text style={styles.gridIcon}>💻</Text>
            <Text style={styles.gridTitle}>LAUNCH TERMINAL</Text>
            <Text style={styles.gridSub}>PowerShell Shell</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.gridCard, styles.specialCard]}
            onPress={handleRecoverGoals}
          >
            <Text style={styles.gridIcon}>🔄</Text>
            <Text style={styles.gridTitle}>RESUME GOALS</Text>
            <Text style={styles.gridSub}>Checkpoint Interlock</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Media & System Audio Deck */}
      <View style={styles.matrixCard}>
        <Text style={styles.sectionLabel}>MEDIA & AUDIO CONTROLS</Text>
        
        <View style={styles.mediaRow}>
          <TouchableOpacity
            style={styles.mediaBtn}
            onPress={() => triggerCommand('media_play_pause')}
          >
            <Text style={styles.mediaIcon}>⏯️</Text>
            <Text style={styles.mediaText}>PLAY/PAUSE</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.mediaBtn}
            onPress={() => triggerCommand('media_next')}
          >
            <Text style={styles.mediaIcon}>⏭️</Text>
            <Text style={styles.mediaText}>NEXT</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.mediaBtn}
            onPress={() => triggerCommand('media_mute')}
          >
            <Text style={styles.mediaIcon}>🔇</Text>
            <Text style={styles.mediaText}>MUTE</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Dangerous Operations Section (Gatekeeper Interlocked) */}
      <View style={[styles.matrixCard, { borderColor: '#ef444430' }]}>
        <Text style={[styles.sectionLabel, { color: '#f87171' }]}>HIGH-RISK OPERATIONS (BIOMETRIC GATE)</Text>
        <View style={styles.grid}>
          <TouchableOpacity
            style={[styles.gridCard, { borderColor: '#ef444440' }]}
            onPress={() => triggerCommand('shutdown')}
          >
            <Text style={styles.gridIcon}>⚡</Text>
            <Text style={[styles.gridTitle, { color: '#f87171' }]}>SHUTDOWN OS</Text>
            <Text style={styles.gridSub}>Requires Biometric Lock</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.gridCard, { borderColor: '#f59e0b40' }]}
            onPress={() => triggerCommand('restart')}
          >
            <Text style={styles.gridIcon}>🔁</Text>
            <Text style={[styles.gridTitle, { color: '#fbbf24' }]}>RESTART OS</Text>
            <Text style={styles.gridSub}>Requires Biometric Lock</Text>
          </TouchableOpacity>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#030712', padding: 16 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 },
  headerTitle: { color: '#f8fafc', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1 },
  headerSubtitle: { color: '#64748b', fontSize: 9, fontFamily: 'monospace', marginTop: 2 },
  lastActionBadge: { backgroundColor: '#00e5ff15', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, borderWidth: 1, borderColor: '#00e5ff30' },
  lastActionText: { color: '#00e5ff', fontSize: 9, fontFamily: 'monospace' },

  liveCard: { backgroundColor: '#0b1329', padding: 14, borderRadius: 14, borderWidth: 1, borderColor: '#00e5ff30', marginBottom: 14 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  liveBadgeRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  dotActive: { backgroundColor: '#00e5ff' },
  dotStandby: { backgroundColor: '#475569' },
  liveTitle: { color: '#f8fafc', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 0.5 },
  liveSubtitle: { color: '#64748b', fontSize: 10, fontFamily: 'monospace', marginTop: 3 },

  promptCard: { backgroundColor: '#0b1329', padding: 16, borderRadius: 14, borderWidth: 1, borderColor: '#1e293b', marginBottom: 14 },
  sectionLabel: { color: '#64748b', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1, marginBottom: 8 },
  textInput: { backgroundColor: '#030712', color: '#f8fafc', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#334155', minHeight: 70, fontFamily: 'monospace', fontSize: 12, lineHeight: 18 },
  chipsScroll: { marginVertical: 10 },
  chip: { backgroundColor: '#030712', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 20, borderWidth: 1, borderColor: '#334155', marginRight: 6 },
  chipText: { color: '#94a3b8', fontSize: 10, fontFamily: 'monospace' },
  
  actionButtonRow: { flexDirection: 'row', gap: 8, marginTop: 4 },
  primarySendBtn: { flex: 2, backgroundColor: '#00e5ff', paddingVertical: 12, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  primarySendText: { color: '#030712', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 0.5 },
  disabledBtn: { opacity: 0.6 },
  voiceMicBtn: { flex: 1, backgroundColor: '#030712', paddingVertical: 12, borderRadius: 10, borderWidth: 1, borderColor: '#00e5ff40', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4 },
  voiceListeningBtn: { backgroundColor: '#dc262625', borderColor: '#ef4444' },
  voiceMicIcon: { fontSize: 13 },
  voiceMicText: { color: '#00e5ff', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },

  matrixCard: { backgroundColor: '#0b1329', padding: 16, borderRadius: 14, borderWidth: 1, borderColor: '#1e293b', marginBottom: 14 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  gridCard: { width: '48%', backgroundColor: '#030712', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#1e293b' },
  specialCard: { borderColor: '#7c3aed40', backgroundColor: '#2e106515' },
  gridIcon: { fontSize: 18, marginBottom: 4 },
  gridTitle: { color: '#f1f5f9', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  gridSub: { color: '#64748b', fontSize: 9, fontFamily: 'monospace', marginTop: 2 },

  mediaRow: { flexDirection: 'row', gap: 8 },
  mediaBtn: { flex: 1, backgroundColor: '#030712', paddingVertical: 12, borderRadius: 10, borderWidth: 1, borderColor: '#1e293b', alignItems: 'center' },
  mediaIcon: { fontSize: 16, marginBottom: 4 },
  mediaText: { color: '#94a3b8', fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace' }
});

