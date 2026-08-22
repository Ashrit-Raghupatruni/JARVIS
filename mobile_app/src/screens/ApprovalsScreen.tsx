import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert, ScrollView, ActivityIndicator } from 'react-native';
import { mobileClient, MobileApprovalItem } from '../api/client';

interface ApprovalLogItem {
  id: string;
  action_type: string;
  decision: string;
  timestamp: number;
}

export default function ApprovalsScreen() {
  const [activeApproval, setActiveApproval] = useState<MobileApprovalItem | null>(null);
  const [timeLeft, setTimeLeft] = useState<number>(30);
  const [recentDecisions, setRecentDecisions] = useState<ApprovalLogItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const checkPending = async () => {
    try {
      setRefreshing(true);
      const res = await mobileClient.fetchPendingApprovals();
      if (res && res.pending_approvals && res.pending_approvals.length > 0) {
        setActiveApproval(res.pending_approvals[0]);
        setTimeLeft(res.pending_approvals[0].timeout_seconds || 30);
      } else {
        setActiveApproval(null);
      }
    } catch (err) {
      console.warn("Failed to check pending approvals:", err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    checkPending();

    // Real-time WebSocket listener for new approval requests
    mobileClient.connectWebSocket(
      () => {},
      (msg) => {
        if (msg.type === "approval_request") {
          setActiveApproval({
            approval_id: msg.approval_id,
            action_type: msg.action_type || "dangerous_action",
            description: msg.description || "Unspecified dangerous operation",
            dangerous_target: msg.dangerous_target || "System Resource",
            timestamp: Date.now(),
            timeout_seconds: msg.timeout_seconds || 30
          });
          setTimeLeft(msg.timeout_seconds || 30);
        }
      }
    );
  }, []);

  // Countdown timer for active approval
  useEffect(() => {
    if (!activeApproval) return;
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setActiveApproval(null);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [activeApproval]);

  const handleDecision = async (decision: 'approve' | 'deny' | 'always_allow' | 'always_deny') => {
    if (!activeApproval) return;
    const targetApproval = activeApproval;
    try {
      await mobileClient.submitApprovalDecision(targetApproval.approval_id, decision);
      setRecentDecisions((prev) => [
        {
          id: targetApproval.approval_id,
          action_type: targetApproval.action_type,
          decision: decision.toUpperCase(),
          timestamp: Date.now()
        },
        ...prev.slice(0, 9)
      ]);
      Alert.alert("Decision Sent", `Action ${decision.toUpperCase()} sent to desktop.`);
      setActiveApproval(null);
    } catch (err) {
      Alert.alert("Error", String(err));
    }
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.headerTitle}>🛡️ SECURITY GATEKEEPER</Text>
        <TouchableOpacity style={styles.refreshBtn} onPress={checkPending} disabled={refreshing}>
          {refreshing ? (
            <ActivityIndicator size="small" color="#00ff66" />
          ) : (
            <Text style={styles.refreshBtnText}>🔄 REFRESH</Text>
          )}
        </TouchableOpacity>
      </View>

      {activeApproval ? (
        <View style={styles.approvalBox}>
          <View style={styles.badgeRow}>
            <Text style={styles.warningBadge}>⚠️ DANGEROUS ACTION DETECTED</Text>
            <View style={styles.timerBadge}>
              <Text style={styles.timerText}>⏳ {timeLeft}s</Text>
            </View>
          </View>

          <Text style={styles.actionType}>{activeApproval.action_type.toUpperCase()}</Text>
          <Text style={styles.description}>{activeApproval.description}</Text>
          <Text style={styles.target}>Target: {activeApproval.dangerous_target}</Text>

          <View style={styles.btnRow}>
            <TouchableOpacity style={styles.approveBtn} onPress={() => handleDecision('approve')}>
              <Text style={styles.btnText}>✅ APPROVE</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.denyBtn} onPress={() => handleDecision('deny')}>
              <Text style={styles.btnText}>❌ DENY</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.btnRow}>
            <TouchableOpacity style={styles.alwaysAllowBtn} onPress={() => handleDecision('always_allow')}>
              <Text style={styles.btnSubText}>🛡️ ALWAYS ALLOW</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.alwaysDenyBtn} onPress={() => handleDecision('always_deny')}>
              <Text style={styles.btnSubText}>⛔ ALWAYS DENY</Text>
            </TouchableOpacity>
          </View>
        </View>
      ) : (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyIcon}>🛡️</Text>
          <Text style={styles.emptyTitle}>NO PENDING APPROVALS</Text>
          <Text style={styles.emptySub}>All critical system and shell actions require mobile confirmation.</Text>
        </View>
      )}

      {/* Recent Decisions Audit Log */}
      {recentDecisions.length > 0 && (
        <View style={styles.auditSection}>
          <Text style={styles.auditTitle}>📋 RECENT DECISIONS AUDIT LOG</Text>
          {recentDecisions.map((log) => (
            <View key={log.id} style={styles.logCard}>
              <View style={styles.logHeader}>
                <Text style={styles.logAction}>{log.action_type}</Text>
                <Text
                  style={[
                    styles.logDecision,
                    log.decision.includes('APPROVE') || log.decision.includes('ALLOW')
                      ? styles.logApproved
                      : styles.logDenied
                  ]}
                >
                  {log.decision}
                </Text>
              </View>
              <Text style={styles.logTime}>{new Date(log.timestamp).toLocaleTimeString()}</Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#050d08', padding: 16 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  headerTitle: { color: '#00ff66', fontSize: 15, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1 },
  refreshBtn: { backgroundColor: '#0a1a0f', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.3)' },
  refreshBtnText: { color: '#00ff66', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  approvalBox: { backgroundColor: '#0a1a0f', padding: 18, borderRadius: 16, borderWidth: 1, borderColor: '#ff9900', marginBottom: 16 },
  badgeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  warningBadge: { color: '#ff9900', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  timerBadge: { backgroundColor: 'rgba(255, 153, 0, 0.2)', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10, borderWidth: 1, borderColor: '#ff9900' },
  timerText: { color: '#ff9900', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  actionType: { color: '#ffffff', fontSize: 16, fontWeight: 'bold', marginBottom: 8, fontFamily: 'monospace' },
  description: { color: '#d0f5df', fontSize: 13, marginBottom: 10, fontFamily: 'monospace' },
  target: { color: '#668877', fontSize: 11, fontFamily: 'monospace', marginBottom: 16 },
  btnRow: { flexDirection: 'row', gap: 10, marginBottom: 10 },
  approveBtn: { flex: 1, backgroundColor: '#00cc52', padding: 12, borderRadius: 10, alignItems: 'center' },
  denyBtn: { flex: 1, backgroundColor: '#ff0055', padding: 12, borderRadius: 10, alignItems: 'center' },
  btnText: { color: '#ffffff', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' },
  alwaysAllowBtn: { flex: 1, backgroundColor: '#0a2215', padding: 10, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: '#00cc52' },
  alwaysDenyBtn: { flex: 1, backgroundColor: '#220a15', padding: 10, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: '#ff0055' },
  btnSubText: { color: '#ffffff', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },
  emptyBox: { backgroundColor: '#0a1a0f', padding: 24, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.15)', alignItems: 'center', marginBottom: 16 },
  emptyIcon: { fontSize: 32, marginBottom: 8 },
  emptyTitle: { color: '#00ff66', fontSize: 14, fontWeight: 'bold', fontFamily: 'monospace' },
  emptySub: { color: '#557090', fontSize: 11, fontFamily: 'monospace', textAlign: 'center', marginTop: 4 },
  auditSection: { marginTop: 8 },
  auditTitle: { color: '#557090', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 8 },
  logCard: { backgroundColor: '#0a1a0f', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.1)', marginBottom: 8 },
  logHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  logAction: { color: '#ffffff', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' },
  logDecision: { fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  logApproved: { backgroundColor: 'rgba(0, 255, 102, 0.2)', color: '#00ff66' },
  logDenied: { backgroundColor: 'rgba(255, 0, 85, 0.2)', color: '#ff0055' },
  logTime: { color: '#557090', fontSize: 10, fontFamily: 'monospace', marginTop: 4 }
});
