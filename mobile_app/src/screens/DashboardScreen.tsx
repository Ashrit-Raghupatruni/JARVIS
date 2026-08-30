import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  DimensionValue
} from 'react-native';
import { mobileClient, SystemTelemetryData, LiveModeFrameData } from '../api/client';

export default function DashboardScreen() {
  const [telemetry, setTelemetry] = useState<SystemTelemetryData | null>(null);
  const [connected, setConnected] = useState(false);
  const [liveFrame, setLiveFrame] = useState<LiveModeFrameData | null>(null);
  const [liveEnabled, setLiveEnabled] = useState(false);
  const [togglingLive, setTogglingLive] = useState(false);

  const fetchLiveStatus = async () => {
    try {
      const res = await mobileClient.fetchLiveModeStatus();
      setLiveEnabled(Boolean(res.live_mode_enabled));
      if (res.frame) {
        setLiveFrame(res.frame);
      } else if (!res.live_mode_enabled) {
        setLiveFrame(null);
      }
    } catch {
      // Background poll
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
            active_app: msg.data.active_app || 'Desktop Workspace',
            window_title: msg.data.window_title || 'Active Window',
            window_bounds: msg.data.window_bounds || null
          });
        }
      }
    );

    fetchLiveStatus();
    const interval = setInterval(fetchLiveStatus, 2500);
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

  const getRadarBoxStyles = (): {
    left: DimensionValue;
    top: DimensionValue;
    width: DimensionValue;
    height: DimensionValue;
  } => {
    if (!liveFrame?.window_bounds) {
      return { left: '15%', top: '15%', width: '70%', height: '70%' };
    }
    const b = liveFrame.window_bounds;
    const normX = Math.max(0, Math.min(1, b.x / 1920));
    const normY = Math.max(0, Math.min(1, b.y / 1080));
    const normW = Math.max(0.2, Math.min(1, b.w / 1920));
    const normH = Math.max(0.2, Math.min(1, b.h / 1080));

    return {
      left: `${normX * 100}%` as DimensionValue,
      top: `${normY * 100}%` as DimensionValue,
      width: `${normW * 100}%` as DimensionValue,
      height: `${normH * 100}%` as DimensionValue
    };
  };

  const getMetricColor = (percent: number): string => {
    if (percent >= 85) return '#ef4444';
    if (percent >= 65) return '#f59e0b';
    return '#00e5ff';
  };

  return (
    <ScrollView style={styles.container}>
      {/* Top HUD Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.brandTitle}>JARVIS OS • HUD</Text>
          <Text style={styles.brandSubtitle}>SYSTEM TELEMETRY & MULTIMODAL RADAR</Text>
        </View>
        <View style={[styles.badge, connected ? styles.onlineBadge : styles.offlineBadge]}>
          <View style={[styles.statusDot, connected ? styles.dotGreen : styles.dotRed]} />
          <Text style={styles.badgeText}>{connected ? 'DESKTOP LINKED' : 'OFFLINE'}</Text>
        </View>
      </View>

      {/* Live Mode Focused Window Spotlight Radar Card */}
      <View style={styles.radarCard}>
        <View style={styles.radarHeader}>
          <View style={styles.radarTitleRow}>
            <View style={[styles.statusDot, liveEnabled ? styles.dotCyan : styles.dotDim]} />
            <Text style={styles.radarCardTitle}>
              {liveEnabled ? 'WINDOW SPOTLIGHT RADAR (ACTIVE)' : 'LIVE CO-PILOT (STANDBY)'}
            </Text>
          </View>

          <TouchableOpacity
            style={[styles.radarToggleBtn, liveEnabled ? styles.radarActiveBtn : styles.radarInactiveBtn]}
            onPress={handleToggleLiveMode}
            disabled={togglingLive}
          >
            {togglingLive ? (
              <ActivityIndicator size="small" color="#030712" />
            ) : (
              <Text style={styles.radarToggleText}>{liveEnabled ? 'DISENGAGE' : 'ENGAGE'}</Text>
            )}
          </TouchableOpacity>
        </View>

        {liveEnabled && liveFrame ? (
          <View style={styles.radarBody}>
            <View style={styles.windowInfoRow}>
              <Text style={styles.appPill}>{liveFrame.active_app || 'Desktop'}</Text>
              <Text style={styles.windowTitleText} numberOfLines={1}>
                {liveFrame.window_title || 'Active Window'}
              </Text>
            </View>

            {liveFrame.proactive_suggestion && (
              <View style={styles.suggestionBox}>
                <Text style={styles.suggestionText}>💡 {liveFrame.proactive_suggestion}</Text>
              </View>
            )}

            {/* Virtual Desktop Radar Grid Canvas */}
            <View style={styles.radarCanvas}>
              <View style={styles.radarCrosshairH} />
              <View style={styles.radarCrosshairV} />
              <View style={[styles.radarTargetBox, getRadarBoxStyles()]}>
                <Text style={styles.radarTargetLabel} numberOfLines={1}>
                  {liveFrame.active_app}
                </Text>
              </View>
            </View>

            {liveFrame.window_bounds && (
              <Text style={styles.boundsMeta}>
                BOUNDS: X={liveFrame.window_bounds.x} Y={liveFrame.window_bounds.y} | {liveFrame.window_bounds.w}×{liveFrame.window_bounds.h} PX
              </Text>
            )}
          </View>
        ) : (
          <Text style={styles.radarIdleText}>
            Autonomous visual co-pilot provides real-time desktop window tracking, target form detection, and proactive suggestions.
          </Text>
        )}
      </View>

      {/* Hardware Telemetry Metric Grid */}
      <Text style={styles.sectionHeader}>HARDWARE TELEMETRY GAUGES</Text>
      
      {telemetry ? (
        <View style={styles.grid}>
          {/* CPU Card */}
          <View style={styles.card}>
            <Text style={styles.cardLabel}>CPU LOAD</Text>
            <Text style={[styles.cardValue, { color: getMetricColor(telemetry.cpu_percent) }]}>
              {telemetry.cpu_percent.toFixed(1)}%
            </Text>
            <View style={styles.barTrack}>
              <View
                style={[
                  styles.barFill,
                  {
                    width: `${Math.min(100, telemetry.cpu_percent)}%`,
                    backgroundColor: getMetricColor(telemetry.cpu_percent)
                  }
                ]}
              />
            </View>
          </View>

          {/* RAM Card */}
          <View style={styles.card}>
            <Text style={styles.cardLabel}>RAM RESIDENT</Text>
            <Text style={[styles.cardValue, { color: getMetricColor(telemetry.ram_percent) }]}>
              {telemetry.ram_percent.toFixed(1)}%
            </Text>
            <View style={styles.barTrack}>
              <View
                style={[
                  styles.barFill,
                  {
                    width: `${Math.min(100, telemetry.ram_percent)}%`,
                    backgroundColor: getMetricColor(telemetry.ram_percent)
                  }
                ]}
              />
            </View>
            <Text style={styles.cardSub}>
              {telemetry.ram_used_gb} GB / {telemetry.ram_total_gb} GB
            </Text>
          </View>

          {/* GPU Card */}
          <View style={styles.card}>
            <Text style={styles.cardLabel}>GPU LOAD</Text>
            <Text style={[styles.cardValue, { color: getMetricColor(telemetry.gpu_percent) }]}>
              {telemetry.gpu_percent.toFixed(1)}%
            </Text>
            <View style={styles.barTrack}>
              <View
                style={[
                  styles.barFill,
                  {
                    width: `${Math.min(100, telemetry.gpu_percent)}%`,
                    backgroundColor: getMetricColor(telemetry.gpu_percent)
                  }
                ]}
              />
            </View>
          </View>

          {/* Battery Card */}
          <View style={styles.card}>
            <Text style={styles.cardLabel}>BATTERY</Text>
            <Text style={styles.cardValue}>
              {telemetry.battery_percent ?? 100}%
            </Text>
            <View style={styles.barTrack}>
              <View
                style={[
                  styles.barFill,
                  {
                    width: `${Math.min(100, telemetry.battery_percent ?? 100)}%`,
                    backgroundColor: '#10b981'
                  }
                ]}
              />
            </View>
            <Text style={styles.cardSub}>
              {telemetry.battery_plugged ? '⚡ Power Adapter Linked' : '🔋 Discharging'}
            </Text>
          </View>

          {/* Active Task & LLM Orchestrator Card */}
          <View style={styles.cardFull}>
            <View style={styles.fullHeader}>
              <Text style={styles.cardLabel}>ACTIVE MISSION CONTROL TASK</Text>
              <View style={styles.llmPill}>
                <Text style={styles.llmPillText}>{telemetry.active_llm_provider.toUpperCase()}</Text>
              </View>
            </View>
            <Text style={styles.cardTask}>{telemetry.active_task || 'Executive Standby — Ready for input'}</Text>
            <View style={styles.taskMetaRow}>
              <Text style={styles.taskMeta}>STATE: {telemetry.assistant_state.toUpperCase()}</Text>
              <Text style={styles.taskMeta}>•</Text>
              <Text style={styles.taskMeta}>{telemetry.internet_connected ? '🌐 WAN ONLINE' : '⚠️ OFFLINE'}</Text>
            </View>
          </View>
        </View>
      ) : (
        <View style={styles.loadingBox}>
          <ActivityIndicator color="#00e5ff" size="small" />
          <Text style={styles.loadingText}>Awaiting desktop telemetry packet stream...</Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#030712', padding: 16 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  brandTitle: { color: '#f8fafc', fontSize: 17, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1.5 },
  brandSubtitle: { color: '#64748b', fontSize: 9, fontFamily: 'monospace', marginTop: 2 },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12 },
  onlineBadge: { backgroundColor: '#05966925', borderWidth: 1, borderColor: '#10b98150' },
  offlineBadge: { backgroundColor: '#dc262625', borderWidth: 1, borderColor: '#ef444450' },
  statusDot: { width: 7, height: 7, borderRadius: 3.5 },
  dotGreen: { backgroundColor: '#10b981' },
  dotRed: { backgroundColor: '#ef4444' },
  dotCyan: { backgroundColor: '#00e5ff' },
  dotDim: { backgroundColor: '#475569' },
  badgeText: { color: '#f8fafc', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },

  radarCard: { backgroundColor: '#0b1329', padding: 16, borderRadius: 16, borderWidth: 1, borderColor: '#00e5ff30', marginBottom: 16 },
  radarHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  radarTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  radarCardTitle: { color: '#00e5ff', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 0.5 },
  radarToggleBtn: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: 8 },
  radarActiveBtn: { backgroundColor: '#ef444425', borderWidth: 1, borderColor: '#ef4444' },
  radarInactiveBtn: { backgroundColor: '#00e5ff', borderWidth: 1, borderColor: '#00e5ff' },
  radarToggleText: { color: '#030712', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },
  radarBody: { marginTop: 12 },
  windowInfoRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  appPill: { backgroundColor: '#00e5ff20', color: '#00e5ff', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace', borderWidth: 1, borderColor: '#00e5ff50' },
  windowTitleText: { color: '#f8fafc', fontSize: 12, fontFamily: 'monospace', flex: 1 },
  suggestionBox: { backgroundColor: '#10b98115', padding: 8, borderRadius: 8, borderWidth: 1, borderColor: '#10b98130', marginBottom: 10 },
  suggestionText: { color: '#34d399', fontSize: 11, fontFamily: 'monospace' },
  radarCanvas: { width: '100%', height: 115, backgroundColor: '#030712', borderRadius: 10, borderWidth: 1, borderColor: '#1e293b', position: 'relative', overflow: 'hidden' },
  radarCrosshairH: { position: 'absolute', top: '50%', left: 0, right: 0, height: 1, backgroundColor: '#1e293b' },
  radarCrosshairV: { position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, backgroundColor: '#1e293b' },
  radarTargetBox: { position: 'absolute', backgroundColor: '#00e5ff25', borderWidth: 1.5, borderColor: '#00e5ff', borderRadius: 6, justifyContent: 'center', alignItems: 'center' },
  radarTargetLabel: { color: '#00e5ff', fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace' },
  boundsMeta: { color: '#64748b', fontSize: 9, fontFamily: 'monospace', marginTop: 6 },
  radarIdleText: { color: '#64748b', fontSize: 11, fontFamily: 'monospace', marginTop: 10, lineHeight: 16 },

  sectionHeader: { color: '#64748b', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1, marginBottom: 10 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  card: { width: '48%', backgroundColor: '#0b1329', padding: 14, borderRadius: 14, borderWidth: 1, borderColor: '#1e293b' },
  cardFull: { width: '100%', backgroundColor: '#0b1329', padding: 14, borderRadius: 14, borderWidth: 1, borderColor: '#1e293b' },
  cardLabel: { color: '#64748b', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },
  cardValue: { color: '#00e5ff', fontSize: 24, fontWeight: 'bold', marginVertical: 4, fontFamily: 'monospace' },
  barTrack: { height: 4, backgroundColor: '#1e293b', borderRadius: 2, overflow: 'hidden', marginVertical: 4 },
  barFill: { height: '100%' },
  cardSub: { color: '#94a3b8', fontSize: 10, fontFamily: 'monospace', marginTop: 4 },
  fullHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  llmPill: { backgroundColor: '#7c3aed25', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, borderWidth: 1, borderColor: '#a855f750' },
  llmPillText: { color: '#c084fc', fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace' },
  cardTask: { color: '#f8fafc', fontSize: 13, fontWeight: 'bold', marginVertical: 6, fontFamily: 'monospace' },
  taskMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  taskMeta: { color: '#64748b', fontSize: 10, fontFamily: 'monospace' },
  loadingBox: { padding: 30, alignItems: 'center', gap: 10 },
  loadingText: { color: '#64748b', fontSize: 11, fontFamily: 'monospace' }
});

