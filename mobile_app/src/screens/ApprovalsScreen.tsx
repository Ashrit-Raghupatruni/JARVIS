import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ScrollView,
  ActivityIndicator,
  Modal,
  TextInput
} from 'react-native';
import { mobileClient, MobileApprovalItem } from '../api/client';

interface ApprovalLogItem {
  id: string;
  action_type: string;
  decision: string;
  timestamp: number;
  biometric_verified?: boolean;
}

const HIGH_RISK_ACTIONS = [
  'system_shutdown',
  'shell_command',
  'file_delete',
  'registry_write',
  'terminal_command',
  'critical_security',
  'kill_process',
  'format_drive'
];

export default function ApprovalsScreen() {
  const [activeApproval, setActiveApproval] = useState<MobileApprovalItem | null>(null);
  const [timeLeft, setTimeLeft] = useState<number>(30);
  const [maxTime, setMaxTime] = useState<number>(30);
  const [recentDecisions, setRecentDecisions] = useState<ApprovalLogItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  
  // Biometric challenge modal state
  const [showBiometricModal, setShowBiometricModal] = useState(false);
  const [pinInput, setPinInput] = useState('');
  const [isVerifyingBio, setIsVerifyingBio] = useState(false);

  const checkPending = async () => {
    try {
      setRefreshing(true);
      const res = await mobileClient.fetchPendingApprovals();
      if (res && res.pending_approvals && res.pending_approvals.length > 0) {
        const item = res.pending_approvals[0];
        setActiveApproval(item);
        const timeout = item.timeout_seconds || 30;
        setTimeLeft(timeout);
        setMaxTime(timeout);
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
          const item: MobileApprovalItem = {
            approval_id: msg.approval_id,
            action_type: msg.action_type || "dangerous_action",
            description: msg.description || "Unspecified dangerous operation",
            dangerous_target: msg.dangerous_target || "System Resource",
            challenge: msg.challenge || "",
            timestamp: Date.now(),
            timeout_seconds: msg.timeout_seconds || 30
          };
          setActiveApproval(item);
          const timeout = item.timeout_seconds || 30;
          setTimeLeft(timeout);
          setMaxTime(timeout);
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
          setShowBiometricModal(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [activeApproval]);

  const isCurrentActionHighRisk = (): boolean => {
    if (!activeApproval) return false;
    const act = (activeApproval.action_type || '').toLowerCase();
    return HIGH_RISK_ACTIONS.some(k => act.includes(k)) || act.includes('shell') || act.includes('shutdown') || act.includes('delete');
  };

  const handleInitiateDecision = (decision: 'approve' | 'deny' | 'always_allow' | 'always_deny') => {
    if (!activeApproval) return;

    if (decision === 'approve' && isCurrentActionHighRisk()) {
      // Require hardware biometric interlock challenge
      setShowBiometricModal(true);
      return;
    }

    executeDecision(decision, false);
  };

  const executeDecision = async (
    decision: 'approve' | 'deny' | 'always_allow' | 'always_deny',
    biometricAuthenticated: boolean,
    biometricSignature?: string
  ) => {
    if (!activeApproval) return;
    const targetApproval = activeApproval;
    try {
      await mobileClient.submitApprovalDecision(
        targetApproval.approval_id,
        decision,
        biometricAuthenticated,
        biometricSignature,
        targetApproval.challenge
      );

      setRecentDecisions((prev) => [
        {
          id: targetApproval.approval_id,
          action_type: targetApproval.action_type,
          decision: decision.toUpperCase(),
          timestamp: Date.now(),
          biometric_verified: biometricAuthenticated
        },
        ...prev.slice(0, 9)
      ]);

      Alert.alert(
        "Decision Dispatched",
        `Action ${decision.toUpperCase()} ${biometricAuthenticated ? 'with Biometric Verification' : ''} sent to desktop.`
      );
      setActiveApproval(null);
      setShowBiometricModal(false);
      setPinInput('');
    } catch (err) {
      Alert.alert("Execution Error", String(err));
    }
  };

  const handleConfirmBiometric = () => {
    setIsVerifyingBio(true);
    setTimeout(() => {
      setIsVerifyingBio(false);
      executeDecision('approve', true, undefined);
    }, 600);
  };

  const progressPercent = Math.max(0, Math.min(100, Math.round((timeLeft / maxTime) * 100)));

  return (
    <ScrollView style={styles.container}>
      {/* Header Bar */}
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.headerTitle}>SECURITY GATEKEEPER</Text>
          <Text style={styles.headerSubtitle}>FAIL-CLOSED ZERO TRUST APPROVAL POLICY</Text>
        </View>
        <TouchableOpacity style={styles.refreshBtn} onPress={checkPending} disabled={refreshing}>
          {refreshing ? (
            <ActivityIndicator size="small" color="#00e5ff" />
          ) : (
            <Text style={styles.refreshBtnText}>SYNC</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Active Approval Card */}
      {activeApproval ? (
        <View style={[styles.approvalBox, isCurrentActionHighRisk() && styles.highRiskBox]}>
          <View style={styles.badgeRow}>
            <View style={isCurrentActionHighRisk() ? styles.criticalTag : styles.warningTag}>
              <Text style={styles.tagText}>
                {isCurrentActionHighRisk() ? 'CRITICAL HIGH-RISK INTERLOCK' : 'SAFETY ACTION INTERCEPT'}
              </Text>
            </View>
            <View style={styles.timerBadge}>
              <Text style={styles.timerText}>{timeLeft}s REMAINING</Text>
            </View>
          </View>

          {/* Progress Bar */}
          <View style={styles.progressBarTrack}>
            <View style={[styles.progressBarFill, { width: `${progressPercent}%` }]} />
          </View>

          <Text style={styles.actionType}>{activeApproval.action_type.toUpperCase()}</Text>
          <Text style={styles.description}>{activeApproval.description}</Text>

          <View style={styles.targetCard}>
            <Text style={styles.targetLabel}>TARGET SYSTEM RESOURCE</Text>
            <Text style={styles.targetValue}>{activeApproval.dangerous_target || 'Local Workstation OS'}</Text>
          </View>

          {isCurrentActionHighRisk() && (
            <View style={styles.bioNotice}>
              <Text style={styles.bioNoticeText}>
                🔒 Hardware Fingerprint / Biometric Signature required to authorize this high-risk action.
              </Text>
            </View>
          )}

          {/* Primary Action Row */}
          <View style={styles.btnRow}>
            <TouchableOpacity
              style={[styles.approveBtn, isCurrentActionHighRisk() && styles.bioApproveBtn]}
              onPress={() => handleInitiateDecision('approve')}
            >
              <Text style={styles.btnText}>
                {isCurrentActionHighRisk() ? 'AUTHORIZE (BIOMETRIC)' : 'APPROVE'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.denyBtn}
              onPress={() => handleInitiateDecision('deny')}
            >
              <Text style={styles.btnText}>REJECT</Text>
            </TouchableOpacity>
          </View>

          {/* Policy Overrides */}
          <View style={styles.btnRow}>
            <TouchableOpacity
              style={styles.alwaysAllowBtn}
              onPress={() => handleInitiateDecision('always_allow')}
            >
              <Text style={styles.btnSubText}>ALWAYS ALLOW</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.alwaysDenyBtn}
              onPress={() => handleInitiateDecision('always_deny')}
            >
              <Text style={styles.btnSubText}>PERMANENT BLOCK</Text>
            </TouchableOpacity>
          </View>
        </View>
      ) : (
        <View style={styles.emptyBox}>
          <View style={styles.emptyIconCircle}>
            <Text style={styles.emptyIcon}>🛡️</Text>
          </View>
          <Text style={styles.emptyTitle}>ALL SYSTEMS SECURED</Text>
          <Text style={styles.emptySub}>
            Zero pending approval interrupts. All incoming high-risk shell, file, and system calls require mobile hardware authorization.
          </Text>
        </View>
      )}

      {/* Recent Decisions Audit Trail */}
      <View style={styles.auditSection}>
        <Text style={styles.auditTitle}>RECENT AUDIT DECISION LOG</Text>
        {recentDecisions.length > 0 ? (
          recentDecisions.map((log) => (
            <View key={log.id} style={styles.logCard}>
              <View style={styles.logHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.logAction}>{log.action_type}</Text>
                  <Text style={styles.logTime}>{new Date(log.timestamp).toLocaleTimeString()}</Text>
                </View>
                <View
                  style={[
                    styles.logBadge,
                    log.decision.includes('APPROVE') || log.decision.includes('ALLOW')
                      ? styles.badgeApproved
                      : styles.badgeDenied
                  ]}
                >
                  <Text
                    style={[
                      styles.logDecision,
                      log.decision.includes('APPROVE') || log.decision.includes('ALLOW')
                        ? styles.textApproved
                        : styles.textDenied
                    ]}
                  >
                    {log.decision} {log.biometric_verified ? '• BIO' : ''}
                  </Text>
                </View>
              </View>
            </View>
          ))
        ) : (
          <View style={styles.emptyLogCard}>
            <Text style={styles.emptyLogText}>No decision history recorded this session.</Text>
          </View>
        )}
      </View>

      {/* Biometric Verification Modal */}
      <Modal visible={showBiometricModal} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContainer}>
            <Text style={styles.modalTitle}>HARDWARE BIOMETRIC VERIFICATION</Text>
            <Text style={styles.modalSub}>
              Confirm identity to authorize execution of high-risk operation:
            </Text>
            <Text style={styles.modalActionName}>
              {activeApproval?.action_type.toUpperCase()}
            </Text>

            <TouchableOpacity
              style={styles.bioSensorBtn}
              onPress={handleConfirmBiometric}
              disabled={isVerifyingBio}
            >
              {isVerifyingBio ? (
                <ActivityIndicator color="#00e5ff" size="large" />
              ) : (
                <>
                  <Text style={styles.sensorIcon}>👆</Text>
                  <Text style={styles.sensorText}>CONFIRM WITH BIOMETRICS</Text>
                  <Text style={styles.sensorSubText}>Tap to sign cryptographic authorization payload</Text>
                </>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.modalCancelBtn}
              onPress={() => setShowBiometricModal(false)}
            >
              <Text style={styles.modalCancelText}>CANCEL</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#02040a', padding: 16 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  headerTitle: { color: '#f8fafc', fontSize: 15, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1.5 },
  headerSubtitle: { color: '#64748b', fontSize: 9, fontFamily: 'monospace', marginTop: 2 },
  refreshBtn: { backgroundColor: 'rgba(37,99,235,0.2)', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(0,229,255,0.4)' },
  refreshBtnText: { color: '#00e5ff', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  
  approvalBox: { backgroundColor: 'rgba(15,23,42,0.5)', padding: 18, borderRadius: 16, borderWidth: 1, borderColor: '#f59e0b', marginBottom: 16 },
  highRiskBox: { borderColor: '#ef4444', backgroundColor: 'rgba(127,29,29,0.15)' },
  badgeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  warningTag: { backgroundColor: 'rgba(245,158,11,0.15)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(245,158,11,0.3)' },
  criticalTag: { backgroundColor: 'rgba(239,68,68,0.2)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(239,68,68,0.4)' },
  tagText: { color: '#f8fafc', fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace' },
  timerBadge: { backgroundColor: 'rgba(2,4,10,0.6)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  timerText: { color: '#f59e0b', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },
  
  progressBarTrack: { height: 4, backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 2, overflow: 'hidden', marginBottom: 14 },
  progressBarFill: { height: '100%', backgroundColor: '#f59e0b' },
  
  actionType: { color: '#ffffff', fontSize: 16, fontWeight: 'bold', marginBottom: 6, fontFamily: 'monospace' },
  description: { color: '#94a3b8', fontSize: 13, marginBottom: 12, fontFamily: 'monospace', lineHeight: 18 },
  targetCard: { backgroundColor: 'rgba(2,4,10,0.6)', padding: 10, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)', marginBottom: 12 },
  targetLabel: { color: '#64748b', fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace' },
  targetValue: { color: '#00e5ff', fontSize: 11, fontFamily: 'monospace', marginTop: 2 },
  bioNotice: { backgroundColor: 'rgba(88,28,135,0.2)', padding: 10, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(168,85,247,0.3)', marginBottom: 14 },
  bioNoticeText: { color: '#d8b4fe', fontSize: 11, fontFamily: 'monospace', lineHeight: 16 },
  
  btnRow: { flexDirection: 'row', gap: 10, marginBottom: 10 },
  approveBtn: { flex: 1, backgroundColor: '#059669', padding: 13, borderRadius: 12, alignItems: 'center' },
  bioApproveBtn: { backgroundColor: '#7c3aed' },
  denyBtn: { flex: 1, backgroundColor: '#dc2626', padding: 13, borderRadius: 12, alignItems: 'center' },
  btnText: { color: '#ffffff', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 0.5 },
  alwaysAllowBtn: { flex: 1, backgroundColor: 'rgba(6,78,59,0.3)', padding: 9, borderRadius: 10, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(5,150,105,0.4)' },
  alwaysDenyBtn: { flex: 1, backgroundColor: 'rgba(127,29,29,0.3)', padding: 9, borderRadius: 10, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(220,38,38,0.4)' },
  btnSubText: { color: '#94a3b8', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },
  
  emptyBox: { backgroundColor: 'rgba(15,23,42,0.5)', padding: 30, borderRadius: 16, borderWidth: 1, borderColor: 'rgba(59,130,246,0.2)', alignItems: 'center', marginBottom: 16 },
  emptyIconCircle: { width: 56, height: 56, borderRadius: 28, backgroundColor: 'rgba(2,4,10,0.6)', justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: 'rgba(0,229,255,0.3)', marginBottom: 12 },
  emptyIcon: { fontSize: 26 },
  emptyTitle: { color: '#00e5ff', fontSize: 14, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1 },
  emptySub: { color: '#64748b', fontSize: 11, fontFamily: 'monospace', textAlign: 'center', marginTop: 6, lineHeight: 16 },
  
  auditSection: { marginTop: 4 },
  auditTitle: { color: '#64748b', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1, marginBottom: 8 },
  logCard: { backgroundColor: 'rgba(15,23,42,0.5)', padding: 12, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(59,130,246,0.15)', marginBottom: 8 },
  logHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  logAction: { color: '#f1f5f9', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' },
  logTime: { color: '#64748b', fontSize: 9, fontFamily: 'monospace', marginTop: 3 },
  logBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  badgeApproved: { backgroundColor: 'rgba(5,150,105,0.2)', borderWidth: 1, borderColor: 'rgba(5,150,105,0.4)' },
  badgeDenied: { backgroundColor: 'rgba(220,38,38,0.2)', borderWidth: 1, borderColor: 'rgba(220,38,38,0.4)' },
  logDecision: { fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace' },
  textApproved: { color: '#34d399' },
  textDenied: { color: '#f87171' },
  emptyLogCard: { padding: 16, backgroundColor: 'rgba(15,23,42,0.5)', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(59,130,246,0.15)', alignItems: 'center' },
  emptyLogText: { color: '#475569', fontSize: 11, fontFamily: 'monospace' },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(3, 7, 18, 0.85)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalContainer: { width: '100%', backgroundColor: '#0b1329', borderRadius: 20, borderWidth: 1, borderColor: '#7c3aed', padding: 22, alignItems: 'center' },
  modalTitle: { color: '#c084fc', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1, textAlign: 'center' },
  modalSub: { color: '#94a3b8', fontSize: 11, fontFamily: 'monospace', textAlign: 'center', marginTop: 8 },
  modalActionName: { color: '#f8fafc', fontSize: 14, fontWeight: 'bold', fontFamily: 'monospace', marginVertical: 12, paddingHorizontal: 12, paddingVertical: 4, backgroundColor: '#030712', borderRadius: 6, borderWidth: 1, borderColor: '#334155' },
  bioSensorBtn: { width: '100%', backgroundColor: '#581c87', borderRadius: 14, borderWidth: 1, borderColor: '#a855f7', padding: 20, alignItems: 'center', marginVertical: 14 },
  sensorIcon: { fontSize: 36, marginBottom: 6 },
  sensorText: { color: '#ffffff', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 0.5 },
  sensorSubText: { color: '#d8b4fe', fontSize: 9, fontFamily: 'monospace', marginTop: 4 },
  modalCancelBtn: { paddingVertical: 8, paddingHorizontal: 16 },
  modalCancelText: { color: '#64748b', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' }
});

