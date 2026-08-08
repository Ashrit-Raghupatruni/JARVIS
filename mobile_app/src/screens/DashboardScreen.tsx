import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { mobileClient, SystemTelemetryData } from '../api/client';

export default function DashboardScreen() {
  const [telemetry, setTelemetry] = useState<SystemTelemetryData | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    mobileClient.connectWebSocket(
      (data) => {
        setTelemetry(data);
        setConnected(true);
      },
      (msg) => console.log("Incoming message:", msg)
    );
  }, []);

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>J.A.R.V.I.S. MOBILE HUD</Text>
        <View style={[styles.badge, connected ? styles.online : styles.offline]}>
          <Text style={styles.badgeText}>{connected ? 'DESKTOP ONLINE' : 'DISCONNECTED'}</Text>
        </View>
      </View>

      {telemetry && (
        <View style={styles.grid}>
          <View style={styles.card}>
            <Text style={styles.cardLabel}>CPU USAGE</Text>
            <Text style={styles.cardValue}>{telemetry.cpu_percent.toFixed(1)}%</Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardLabel}>RAM USAGE</Text>
            <Text style={styles.cardValue}>{telemetry.ram_percent.toFixed(1)}%</Text>
            <Text style={styles.cardSub}>{telemetry.ram_used_gb} GB / {telemetry.ram_total_gb} GB</Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardLabel}>GPU USAGE</Text>
            <Text style={styles.cardValue}>{telemetry.gpu_percent.toFixed(1)}%</Text>
          </View>

          <View style={styles.cardFull}>
            <Text style={styles.cardLabel}>ACTIVE DESKTOP TASK</Text>
            <Text style={styles.cardTask}>{telemetry.active_task}</Text>
            <Text style={styles.cardSub}>LLM Provider: {telemetry.active_llm_provider}</Text>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#050d08', padding: 16 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
  title: { color: '#00ff66', fontSize: 18, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 2 },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  online: { backgroundColor: 'rgba(0, 255, 102, 0.2)', borderWidth: 1, borderColor: '#00ff66' },
  offline: { backgroundColor: 'rgba(255, 0, 85, 0.2)', borderWidth: 1, borderColor: '#ff0055' },
  badgeText: { color: '#ffffff', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  card: { width: '48%', backgroundColor: '#0a1a0f', padding: 16, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)' },
  cardFull: { width: '100%', backgroundColor: '#0a1a0f', padding: 16, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)', marginTop: 8 },
  cardLabel: { color: '#668877', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  cardValue: { color: '#00ff66', fontSize: 24, fontWeight: 'bold', marginVertical: 4, fontFamily: 'monospace' },
  cardTask: { color: '#ffffff', fontSize: 15, fontWeight: 'bold', marginVertical: 4, fontFamily: 'monospace' },
  cardSub: { color: '#00cc52', fontSize: 11, fontFamily: 'monospace' }
});
