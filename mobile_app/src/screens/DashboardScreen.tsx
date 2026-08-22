import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, DimensionValue } from 'react-native';
import { mobileClient, SystemTelemetryData, LiveModeFrameData } from '../api/client';

export default function DashboardScreen() {
  const [telemetry, setTelemetry] = useState<SystemTelemetryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [liveFrame, setLiveFrame] = useState<LiveModeFrameData | null>(null);
  const [liveEnabled, setLiveEnabled] = useState(false);
  const [togglingLive, setTogglingLive] = useState(false);

  // Poll Live Mode status
  const fetchLiveStatus = async () => {
    try {
      const res = await mobileClient.fetchLiveModeStatus();
      setLiveEnabled(Boolean(res.live_mode_enabled));
      if (res.frame) {
        setLiveFrame(res.frame);
      } else if (!res.live_mode_enabled) {
        setLiveFrame(null);
      }
    } catch (err) {
      // Background poll notice
    }
  };

  useEffect(() => {
    mobileClient.connectWebSocket(
      (data) => {
        setTelemetry(data);
        setConnected(true);
      },
      (msg) => {
        if (msg.type === 'live_mode_status' && msg.data) {
          setLiveEnabled(Boolean(msg.data.is_active));
          setLiveFrame({
            is_live_mode_enabled: Boolean(msg.data.is_active),
            active_app: msg.data.active_app || 'Desktop',
            window_title: msg.data.window_title || 'Active Window',
            window_bounds: msg.data.window_bounds || null
          });
        }
      }
    );

    fetchLiveStatus();
    const interval = setInterval(fetchLiveStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleLiveMode = async () => {
    setTogglingLive(true);
    try {
      const nextState = !liveEnabled;
      const res = await mobileClient.toggleLiveMode(nextState);
      setLiveEnabled(Boolean(res.live_mode_enabled));
      fetchLiveStatus();
    } catch (err) {
      console.log('Error toggling live mode:', err);
    } finally {
      setTogglingLive(false);
    }
  };

  // Helper to calculate radar rectangle positioning (normalized to 1920x1080 virtual desktop)
  const getRadarBoxStyles = (): {
    left: DimensionValue;
    top: DimensionValue;
    width: DimensionValue;
    height: DimensionValue;
  } => {
    if (!liveFrame?.window_bounds) {
      return { left: '10%', top: '10%', width: '80%', height: '80%' };
    }
    const b = liveFrame.window_bounds;
    // Clamp to 0..1920, 0..1080
    const normX = Math.max(0, Math.min(1, b.x / 1920));
    const normY = Math.max(0, Math.min(1, b.y / 1080));
    const normW = Math.max(0.15, Math.min(1, b.w / 1920));
    const normH = Math.max(0.15, Math.min(1, b.h / 1080));

    return {
      left: `${normX * 100}%` as DimensionValue,
      top: `${normY * 100}%` as DimensionValue,
      width: `${normW * 100}%` as DimensionValue,
      height: `${normH * 100}%` as DimensionValue
    };
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>J.A.R.V.I.S. MOBILE HUD</Text>
        <View style={[styles.badge, connected ? styles.online : styles.offline]}>
          <Text style={styles.badgeText}>{connected ? 'DESKTOP ONLINE' : 'DISCONNECTED'}</Text>
        </View>
      </View>

      {/* ── LIVE MODE & FOCUSED WINDOW SPOTLIGHT RADAR CARD ── */}
      <View style={styles.liveCard}>
        <View style={styles.liveCardHeader}>
          <View style={styles.liveTitleRow}>
            <View style={[styles.liveDot, liveEnabled ? styles.liveDotActive : styles.liveDotInactive]} />
            <Text style={styles.liveCardTitle}>
              {liveEnabled ? 'LIVE MODE: ACTIVE FOCUS' : 'LIVE MODE: STANDING BY'}
            </Text>
          </View>
          <TouchableOpacity
            style={[styles.liveToggleBtn, liveEnabled ? styles.liveToggleBtnActive : styles.liveToggleBtnInactive]}
            onPress={handleToggleLiveMode}
            disabled={togglingLive}
          >
            {togglingLive ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <Text style={styles.liveToggleBtnText}>{liveEnabled ? 'DISABLE' : 'ENABLE'}</Text>
            )}
          </TouchableOpacity>
        </View>

        {liveEnabled && liveFrame ? (
          <View style={styles.liveDetails}>
            {/* Active Window Metadata */}
            <View style={styles.liveMetaRow}>
              <Text style={styles.liveAppBadge}>{liveFrame.active_app || 'Desktop'}</Text>
              <Text style={styles.liveWindowTitle} numberOfLines={1}>
                {liveFrame.window_title || 'Active Workspace'}
              </Text>
            </View>

            {liveFrame.active_workflow && (
              <Text style={styles.workflowText}>⚙️ {liveFrame.active_workflow}</Text>
            )}
            {liveFrame.proactive_suggestion && (
              <View style={styles.suggestionBox}>
                <Text style={styles.suggestionText}>💡 {liveFrame.proactive_suggestion}</Text>
              </View>
            )}

            {/* Virtual Desktop Mini-Map / Radar Spotlight Frame */}
            <View style={styles.radarContainer}>
              <View style={styles.radarScreenFrame}>
                {/* Virtual screen grid scanlines */}
                <View style={styles.radarGridLineH} />
                <View style={styles.radarGridLineV} />

                {/* Focused Window Highlight Rectangle */}
                <View style={[styles.radarWindowBox, getRadarBoxStyles()]}>
                  <Text style={styles.radarWindowLabel} numberOfLines={1}>
                    {liveFrame.active_app}
                  </Text>
                </View>
              </View>

              {/* Window Geometry Tag */}
              {liveFrame.window_bounds && (
                <Text style={styles.boundsText}>
                  BOUNDS: X={liveFrame.window_bounds.x} Y={liveFrame.window_bounds.y} | {liveFrame.window_bounds.w}×{liveFrame.window_bounds.h} px
                </Text>
              )}
            </View>
          </View>
        ) : (
          <Text style={styles.liveIdleText}>
            Live Mode streams active window focus coordinates, application workflows, and proactive suggestions.
          </Text>
        )}
      </View>

      {/* ── SYSTEM TELEMETRY METRICS ── */}
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

          <View style={styles.card}>
            <Text style={styles.cardLabel}>BATTERY</Text>
            <Text style={styles.cardValue}>{telemetry.battery_percent ?? 85}%</Text>
            <Text style={styles.cardSub}>{telemetry.battery_plugged ? '⚡ Charging' : '🔋 On Battery'}</Text>
          </View>

          <View style={styles.cardFull}>
            <Text style={styles.cardLabel}>ACTIVE DESKTOP TASK</Text>
            <Text style={styles.cardTask}>{telemetry.active_task || 'Mission Control Active'}</Text>
            <Text style={styles.cardSub}>LLM Provider: {telemetry.active_llm_provider}</Text>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#050d08', padding: 16 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  title: { color: '#00ff66', fontSize: 18, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 2 },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  online: { backgroundColor: 'rgba(0, 255, 102, 0.2)', borderWidth: 1, borderColor: '#00ff66' },
  offline: { backgroundColor: 'rgba(255, 0, 85, 0.2)', borderWidth: 1, borderColor: '#ff0055' },
  badgeText: { color: '#ffffff', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },
  liveCard: { backgroundColor: '#0a1a0f', padding: 16, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(0, 229, 255, 0.3)', marginBottom: 16 },
  liveCardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  liveTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  liveDot: { width: 8, height: 8, borderRadius: 4 },
  liveDotActive: { backgroundColor: '#00e5ff' },
  liveDotInactive: { backgroundColor: '#557090' },
  liveCardTitle: { color: '#00e5ff', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1 },
  liveToggleBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, borderWidth: 1 },
  liveToggleBtnActive: { backgroundColor: 'rgba(255, 0, 85, 0.2)', borderColor: '#ff0055' },
  liveToggleBtnInactive: { backgroundColor: 'rgba(0, 229, 255, 0.2)', borderColor: '#00e5ff' },
  liveToggleBtnText: { color: '#ffffff', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },
  liveDetails: { marginTop: 12 },
  liveMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  liveAppBadge: { backgroundColor: 'rgba(0, 229, 255, 0.2)', color: '#00e5ff', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace', borderWidth: 1, borderColor: 'rgba(0, 229, 255, 0.4)' },
  liveWindowTitle: { color: '#ffffff', fontSize: 12, fontFamily: 'monospace', flex: 1 },
  workflowText: { color: '#88ccbb', fontSize: 11, fontFamily: 'monospace', marginBottom: 6 },
  suggestionBox: { backgroundColor: 'rgba(0, 255, 102, 0.1)', padding: 8, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.25)', marginBottom: 10 },
  suggestionText: { color: '#00ff66', fontSize: 11, fontFamily: 'monospace' },
  radarContainer: { marginTop: 6, alignItems: 'center' },
  radarScreenFrame: { width: '100%', height: 110, backgroundColor: '#030805', borderRadius: 8, borderWidth: 1, borderColor: 'rgba(0, 229, 255, 0.4)', position: 'relative', overflow: 'hidden' },
  radarGridLineH: { position: 'absolute', top: '50%', left: 0, right: 0, height: 1, backgroundColor: 'rgba(0, 229, 255, 0.1)' },
  radarGridLineV: { position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, backgroundColor: 'rgba(0, 229, 255, 0.1)' },
  radarWindowBox: { position: 'absolute', backgroundColor: 'rgba(0, 229, 255, 0.25)', borderWidth: 1.5, borderColor: '#00e5ff', borderRadius: 4, padding: 2, justifyContent: 'center', alignItems: 'center' },
  radarWindowLabel: { color: '#00e5ff', fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace' },
  boundsText: { color: '#557090', fontSize: 9, fontFamily: 'monospace', marginTop: 4 },
  liveIdleText: { color: '#668877', fontSize: 11, fontFamily: 'monospace', marginTop: 8, lineHeight: 16 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  card: { width: '48%', backgroundColor: '#0a1a0f', padding: 14, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)' },
  cardFull: { width: '100%', backgroundColor: '#0a1a0f', padding: 14, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)' },
  cardLabel: { color: '#668877', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  cardValue: { color: '#00ff66', fontSize: 22, fontWeight: 'bold', marginVertical: 4, fontFamily: 'monospace' },
  cardTask: { color: '#ffffff', fontSize: 14, fontWeight: 'bold', marginVertical: 4, fontFamily: 'monospace' },
  cardSub: { color: '#00cc52', fontSize: 11, fontFamily: 'monospace' }
});
