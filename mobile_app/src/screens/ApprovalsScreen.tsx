import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { mobileClient, MobileApprovalItem } from '../api/client';

export default function ApprovalsScreen() {
  const [activeApproval, setActiveApproval] = useState<MobileApprovalItem | null>({
    approval_id: "appr_101",
    action_type: "terminal_command",
    description: "Execute: python backend/scripts/backup.py --force",
    dangerous_target: "C:\\Users\\ashri\\JARVIS\\data",
    timestamp: Date.now(),
    timeout_seconds: 30
  });

  const handleDecision = async (decision: 'approve' | 'deny' | 'always_allow' | 'always_deny') => {
    if (!activeApproval) return;
    try {
      await mobileClient.submitApprovalDecision(activeApproval.approval_id, decision);
      Alert.alert("Decision Sent", `Action ${decision.toUpperCase()} sent to desktop.`);
      setActiveApproval(null);
    } catch (err) {
      Alert.alert("Error", String(err));
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.headerTitle}>SECURITY GATEKEEPER APPROVALS</Text>

      {activeApproval ? (
        <View style={styles.approvalBox}>
          <Text style={styles.warningBadge}>⚠️ DANGEROUS ACTION DETECTED</Text>
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
          <Text style={styles.emptyText}>✓ NO PENDING APPROVALS</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#050d08', padding: 16 },
  headerTitle: { color: '#00ff66', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 20 },
  approvalBox: { backgroundColor: '#0a1a0f', padding: 20, borderRadius: 16, borderWidth: 1, borderColor: '#ff9900' },
  warningBadge: { color: '#ff9900', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 8 },
  actionType: { color: '#ffffff', fontSize: 18, fontWeight: 'bold', marginBottom: 8, fontFamily: 'monospace' },
  description: { color: '#d0f5df', fontSize: 14, marginBottom: 12 },
  target: { color: '#668877', fontSize: 11, fontFamily: 'monospace', marginBottom: 20 },
  btnRow: { flexDirection: 'row', gap: 10, marginBottom: 10 },
  approveBtn: { flex: 1, backgroundColor: '#00cc52', padding: 14, borderRadius: 10, alignItems: 'center' },
  denyBtn: { flex: 1, backgroundColor: '#ff0055', padding: 14, borderRadius: 10, alignItems: 'center' },
  alwaysAllowBtn: { flex: 1, backgroundColor: 'rgba(0, 204, 82, 0.2)', borderWidth: 1, borderColor: '#00cc52', padding: 10, borderRadius: 8, alignItems: 'center' },
  alwaysDenyBtn: { flex: 1, backgroundColor: 'rgba(255, 0, 85, 0.2)', borderWidth: 1, borderColor: '#ff0055', padding: 10, borderRadius: 8, alignItems: 'center' },
  btnText: { color: '#ffffff', fontSize: 14, fontWeight: 'bold', fontFamily: 'monospace' },
  btnSubText: { color: '#ffffff', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  emptyBox: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyText: { color: '#00ff66', fontSize: 14, fontWeight: 'bold', fontFamily: 'monospace' }
});
