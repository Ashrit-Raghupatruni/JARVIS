import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
  ScrollView,
  ActivityIndicator
} from 'react-native';
import { mobileClient } from '../api/client';

interface OAuthStatusState {
  google?: boolean;
  microsoft?: boolean;
  github?: boolean;
  slack?: boolean;
  notion?: boolean;
}

export default function PairingScreen() {
  const [host, setHost] = useState('10.1.166.115');
  const [port, setPort] = useState('8000');
  const [pin, setPin] = useState('');
  const [deviceName, setDeviceName] = useState('Android Companion');
  const [isPaired, setIsPaired] = useState(false);
  const [loading, setLoading] = useState(false);
  const [scanningMDNS, setScanningMDNS] = useState(false);
  const [mdnsStatus, setMdnsStatus] = useState<string | null>(null);
  const [qrPayload, setQrPayload] = useState('');
  const [oauthStatus, setOauthStatus] = useState<OAuthStatusState>({});

  const saveConnection = () => {
    const portNum = parseInt(port, 10) || 8000;
    mobileClient.setServerAddress(host, portNum);
    setMdnsStatus(`Manual address saved: ${host}:${portNum}`);
  };

  const loadOAuth = async () => {
    try {
      const res = await mobileClient.fetchOAuthStatus();
      if (res && res.providers) {
        setOauthStatus({
          google: Boolean(res.providers.google?.connected),
          microsoft: Boolean(res.providers.microsoft?.connected),
          github: Boolean(res.providers.github?.connected),
          slack: Boolean(res.providers.slack?.connected),
          notion: Boolean(res.providers.notion?.connected)
        });
      }
    } catch {
      // Background poll
    }
  };

  useEffect(() => {
    loadOAuth();
  }, []);

  const handleAutoDiscover = async () => {
    setScanningMDNS(true);
    setMdnsStatus("Broadcasting mDNS query for _jarvis._tcp.local. on LAN...");
    try {
      const discovered = await mobileClient.autoDiscoverServer([host]);
      if (discovered) {
        setHost(discovered.host);
        setPort(String(discovered.port));
        setMdnsStatus(`✓ Discovered JARVIS desktop at ${discovered.host}:${discovered.port}`);
        Alert.alert("✓ mDNS Discovery Successful", `Found active JARVIS desktop node at ${discovered.host}:${discovered.port}!`);
        loadOAuth();
      } else {
        setMdnsStatus("No responsive node found via mDNS probe. Check local Wi-Fi.");
        Alert.alert("mDNS Discovery", "Could not automatically resolve JARVIS node. Verify desktop is running on same Wi-Fi and port 8000 is open.");
      }
    } catch (e) {
      setMdnsStatus(`Discovery error: ${e}`);
    } finally {
      setScanningMDNS(false);
    }
  };

  const handleQRPairing = async (customPayload?: string) => {
    const payloadToUse = (typeof customPayload === 'string' ? customPayload : qrPayload).trim();
    if (!payloadToUse) {
      Alert.alert("QR Error", "Please enter or paste the QR pairing payload (e.g. jarvis_pair://sess_...:123456)");
      return;
    }

    setLoading(true);
    try {
      saveConnection();
      const res = await mobileClient.pairWithQR(payloadToUse, deviceName);
      if (res && (res.access_token || res.token || res.status === 'paired')) {
        setIsPaired(true);
        Alert.alert("✓ QR Paired Successfully", `Device '${deviceName}' authenticated via QR Code!`);
        loadOAuth();
      } else {
        Alert.alert("QR Pairing Failed", res.detail || res.message || "Invalid or expired QR payload.");
      }
    } catch (err) {
      Alert.alert("QR Pairing Exception", String(err));
    } finally {
      setLoading(false);
    }
  };

  const handlePairing = async () => {
    if (!pin.trim()) {
      Alert.alert("Pairing Error", "Please enter the 6-digit PIN displayed on your desktop screen.");
      return;
    }

    setLoading(true);
    try {
      saveConnection();
      const res = await mobileClient.easyPair(pin.trim(), deviceName);
      if (res && (res.token || res.status === 'paired')) {
        setIsPaired(true);
        Alert.alert("✓ Paired Successfully", `Device '${deviceName}' paired with JARVIS OS!`);
        loadOAuth();
      } else {
        Alert.alert("Pairing Failed", res.message || "Invalid or expired pairing PIN.");
      }
    } catch (err) {
      Alert.alert("Pairing Exception", String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Header */}
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.headerTitle}>SECURE NETWORK PAIRING</Text>
          <Text style={styles.headerSubtitle}>ZERO-TRUST CRYPTOGRAPHIC DEVICE LINK</Text>
        </View>
        <View style={[styles.statusBadge, isPaired ? styles.badgePaired : styles.badgeUnpaired]}>
          <Text style={styles.statusBadgeText}>{isPaired ? 'DEVICE TRUSTED' : 'UNLINKED'}</Text>
        </View>
      </View>

      {/* ── SECTION 1: mDNS LAN AUTO-DISCOVERY ── */}
      <View style={styles.sectionCard}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardIcon}>📡</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>mDNS LAN AUTO-DISCOVERY</Text>
            <Text style={styles.cardSub}>Zero manual IP configuration via _jarvis._tcp broadcast</Text>
          </View>
        </View>

        <TouchableOpacity
          style={styles.mdnsScanBtn}
          onPress={handleAutoDiscover}
          disabled={scanningMDNS}
        >
          {scanningMDNS ? (
            <ActivityIndicator color="#030712" size="small" />
          ) : (
            <Text style={styles.mdnsScanText}>⚡ AUTO-SCAN LOCAL NETWORK (mDNS)</Text>
          )}
        </TouchableOpacity>

        {mdnsStatus && (
          <View style={styles.mdnsStatusBox}>
            <Text style={styles.mdnsStatusText}>{mdnsStatus}</Text>
          </View>
        )}

        <View style={styles.ipRow}>
          <View style={{ flex: 3, marginRight: 8 }}>
            <Text style={styles.fieldLabel}>Desktop Host IP:</Text>
            <TextInput
              style={styles.input}
              value={host}
              onChangeText={setHost}
              placeholder="10.1.166.115"
              placeholderTextColor="#475569"
            />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.fieldLabel}>Port:</Text>
            <TextInput
              style={styles.input}
              value={port}
              onChangeText={setPort}
              keyboardType="numeric"
              placeholder="8000"
              placeholderTextColor="#475569"
            />
          </View>
        </View>

        <TouchableOpacity style={styles.saveIpBtn} onPress={saveConnection}>
          <Text style={styles.saveIpText}>💾 SAVE HOST CONFIGURATION</Text>
        </TouchableOpacity>
      </View>

      {/* ── SECTION 2: 6-DIGIT PIN AUTHENTICATION ── */}
      <View style={styles.sectionCard}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardIcon}>🔑</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>6-DIGIT DESKTOP PIN AUTH</Text>
            <Text style={styles.cardSub}>Enter the 6-digit PIN shown on your desktop screen</Text>
          </View>
        </View>

        <Text style={styles.fieldLabel}>Device Friendly Name:</Text>
        <TextInput
          style={styles.input}
          value={deviceName}
          onChangeText={setDeviceName}
        />

        <Text style={styles.fieldLabel}>Pairing PIN:</Text>
        <TextInput
          style={[styles.input, styles.pinInput]}
          value={pin}
          onChangeText={setPin}
          keyboardType="numeric"
          maxLength={6}
          placeholder="000000"
          placeholderTextColor="#334155"
        />

        <TouchableOpacity style={styles.primaryPairBtn} onPress={handlePairing} disabled={loading}>
          {loading ? (
            <ActivityIndicator color="#030712" size="small" />
          ) : (
            <Text style={styles.primaryPairText}>🔒 AUTHENTICATE DEVICE</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* ── SECTION 3: CLOUD ECOSYSTEM INTEGRATIONS STATUS ── */}
      <View style={styles.sectionCard}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardIcon}>🌐</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>DIRECT OAUTH2 INTEGRATIONS (PKCE)</Text>
            <Text style={styles.cardSub}>Synced enterprise cloud accounts on desktop</Text>
          </View>
        </View>

        <View style={styles.oauthGrid}>
          <View style={styles.oauthItem}>
            <Text style={styles.oauthName}>Google Workspace</Text>
            <View style={[styles.oauthPill, oauthStatus.google ? styles.pillConnected : styles.pillDisconnected]}>
              <Text style={styles.oauthPillText}>{oauthStatus.google ? 'LINKED' : 'OFFLINE'}</Text>
            </View>
          </View>

          <View style={styles.oauthItem}>
            <Text style={styles.oauthName}>Microsoft 365</Text>
            <View style={[styles.oauthPill, oauthStatus.microsoft ? styles.pillConnected : styles.pillDisconnected]}>
              <Text style={styles.oauthPillText}>{oauthStatus.microsoft ? 'LINKED' : 'OFFLINE'}</Text>
            </View>
          </View>

          <View style={styles.oauthItem}>
            <Text style={styles.oauthName}>GitHub Enterprise</Text>
            <View style={[styles.oauthPill, oauthStatus.github ? styles.pillConnected : styles.pillDisconnected]}>
              <Text style={styles.oauthPillText}>{oauthStatus.github ? 'LINKED' : 'OFFLINE'}</Text>
            </View>
          </View>

          <View style={styles.oauthItem}>
            <Text style={styles.oauthName}>Slack Workspace</Text>
            <View style={[styles.oauthPill, oauthStatus.slack ? styles.pillConnected : styles.pillDisconnected]}>
              <Text style={styles.oauthPillText}>{oauthStatus.slack ? 'LINKED' : 'OFFLINE'}</Text>
            </View>
          </View>

          <View style={styles.oauthItem}>
            <Text style={styles.oauthName}>Notion Workspace</Text>
            <View style={[styles.oauthPill, oauthStatus.notion ? styles.pillConnected : styles.pillDisconnected]}>
              <Text style={styles.oauthPillText}>{oauthStatus.notion ? 'LINKED' : 'OFFLINE'}</Text>
            </View>
          </View>
        </View>
      </View>

      {/* ── SECTION 4: SUB-AGENT QUOTA SANDBOX LIMITS ── */}
      <View style={styles.sectionCard}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardIcon}>⚙️</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>SUB-AGENT EXECUTION SANDBOX</Text>
            <Text style={styles.cardSub}>Process tree resource quotas & checkpoint interlock</Text>
          </View>
        </View>

        <View style={styles.quotaRow}>
          <View style={styles.quotaBox}>
            <Text style={styles.quotaLabel}>MEMORY CEILING</Text>
            <Text style={styles.quotaValue}>512 MB RSS</Text>
          </View>
          <View style={styles.quotaBox}>
            <Text style={styles.quotaLabel}>CPU TIME LIMIT</Text>
            <Text style={styles.quotaValue}>30.0 SECONDS</Text>
          </View>
          <View style={styles.quotaBox}>
            <Text style={styles.quotaLabel}>RECOVERY LOCK</Text>
            <Text style={[styles.quotaValue, { color: '#00e5ff' }]}>ACTIVE</Text>
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#030712', padding: 16 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  headerTitle: { color: '#f8fafc', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1 },
  headerSubtitle: { color: '#64748b', fontSize: 9, fontFamily: 'monospace', marginTop: 2 },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  badgePaired: { backgroundColor: '#05966925', borderWidth: 1, borderColor: '#10b981' },
  badgeUnpaired: { backgroundColor: '#33415530', borderWidth: 1, borderColor: '#475569' },
  statusBadgeText: { color: '#f8fafc', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },

  sectionCard: { backgroundColor: '#0b1329', padding: 16, borderRadius: 16, borderWidth: 1, borderColor: '#1e293b', marginBottom: 16 },
  cardHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  cardIcon: { fontSize: 20 },
  cardTitle: { color: '#f8fafc', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 0.5 },
  cardSub: { color: '#64748b', fontSize: 10, fontFamily: 'monospace', marginTop: 2 },

  mdnsScanBtn: { backgroundColor: '#00e5ff', paddingVertical: 12, borderRadius: 10, alignItems: 'center', marginVertical: 8 },
  mdnsScanText: { color: '#030712', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 0.5 },
  mdnsStatusBox: { backgroundColor: '#030712', padding: 10, borderRadius: 8, borderWidth: 1, borderColor: '#00e5ff30', marginBottom: 10 },
  mdnsStatusText: { color: '#00e5ff', fontSize: 10, fontFamily: 'monospace' },

  ipRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 8 },
  fieldLabel: { color: '#64748b', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 4 },
  input: { backgroundColor: '#030712', color: '#f8fafc', borderRadius: 8, padding: 10, borderWidth: 1, borderColor: '#334155', fontFamily: 'monospace', fontSize: 12 },
  pinInput: { fontSize: 26, letterSpacing: 8, textAlign: 'center', fontWeight: 'bold', color: '#00e5ff', paddingVertical: 12 },
  saveIpBtn: { backgroundColor: '#030712', borderWidth: 1, borderColor: '#334155', paddingVertical: 10, borderRadius: 8, alignItems: 'center', marginTop: 8 },
  saveIpText: { color: '#94a3b8', fontSize: 10, fontWeight: 'bold', fontFamily: 'monospace' },

  primaryPairBtn: { backgroundColor: '#10b981', paddingVertical: 13, borderRadius: 10, alignItems: 'center', marginTop: 12 },
  primaryPairText: { color: '#030712', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 0.5 },

  oauthGrid: { gap: 8, marginTop: 4 },
  oauthItem: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#030712', padding: 10, borderRadius: 8, borderWidth: 1, borderColor: '#1e293b' },
  oauthName: { color: '#e2e8f0', fontSize: 11, fontFamily: 'monospace' },
  oauthPill: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  pillConnected: { backgroundColor: '#05966925', borderWidth: 1, borderColor: '#10b981' },
  pillDisconnected: { backgroundColor: '#33415530', borderWidth: 1, borderColor: '#475569' },
  oauthPillText: { fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace', color: '#f8fafc' },

  quotaRow: { flexDirection: 'row', gap: 8, marginTop: 4 },
  quotaBox: { flex: 1, backgroundColor: '#030712', padding: 10, borderRadius: 8, borderWidth: 1, borderColor: '#1e293b', alignItems: 'center' },
  quotaLabel: { color: '#64748b', fontSize: 8, fontWeight: 'bold', fontFamily: 'monospace' },
  quotaValue: { color: '#f8fafc', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace', marginTop: 4 }
});


