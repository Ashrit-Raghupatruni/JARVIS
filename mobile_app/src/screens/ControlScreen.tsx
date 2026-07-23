import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { mobileClient } from '../api/client';

export default function ControlScreen() {
  const triggerCommand = async (cmd: string, params = {}) => {
    try {
      const res = await mobileClient.sendRemoteCommand(cmd, params);
      Alert.alert("Command Dispatched", JSON.stringify(res));
    } catch (err) {
      Alert.alert("Execution Failed", String(err));
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.headerTitle}>REMOTE DESKTOP COMMANDS</Text>

      <View style={styles.grid}>
        <TouchableOpacity style={[styles.cmdCard, styles.danger]} onPress={() => triggerCommand('shutdown')}>
          <Text style={styles.cmdTitle}>SHUTDOWN PC</Text>
          <Text style={styles.cmdSub}>Power off desktop</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.cmdCard, styles.warning]} onPress={() => triggerCommand('restart')}>
          <Text style={styles.cmdTitle}>RESTART PC</Text>
          <Text style={styles.cmdSub}>Reboot operating system</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.cmdCard} onPress={() => triggerCommand('lock')}>
          <Text style={styles.cmdTitle}>LOCK WORKSTATION</Text>
          <Text style={styles.cmdSub}>Secure lock screen</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.cmdCard} onPress={() => triggerCommand('open_app', { app_name: 'code' })}>
          <Text style={styles.cmdTitle}>LAUNCH VS CODE</Text>
          <Text style={styles.cmdSub}>Open IDE workspace</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#050811', padding: 16 },
  headerTitle: { color: '#00e5ff', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 20 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  cmdCard: { width: '48%', backgroundColor: '#0e1726', padding: 16, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(0, 229, 255, 0.2)' },
  danger: { borderColor: '#ff0055' },
  warning: { borderColor: '#ff9900' },
  cmdTitle: { color: '#ffffff', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace' },
  cmdSub: { color: '#88a0c0', fontSize: 10, marginTop: 4 }
});
