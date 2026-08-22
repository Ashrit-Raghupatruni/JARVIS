import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, Alert, ScrollView } from 'react-native';
import { mobileClient } from '../api/client';

export default function PairingScreen() {
  const [host, setHost] = useState('10.200.40.177');
  const [port, setPort] = useState('8000');
  const [pin, setPin] = useState('');
  const [deviceName, setDeviceName] = useState('Android Companion');
  const [isPaired, setIsPaired] = useState(false);
  const [loading, setLoading] = useState(false);
  const [qrPayload, setQrPayload] = useState('');

  const saveConnection = () => {
    const portNum = parseInt(port, 10) || 8000;
    mobileClient.setServerAddress(host, portNum);
  };

  const handleQRPairing = async (customPayload?: string) => {
    const payloadToUse = (typeof customPayload === 'string' ? customPayload : qrPayload).trim();
    if (!payloadToUse) {
      Alert.alert("QR Error", "Please paste or enter the QR pairing payload (e.g. jarvis_pair://sess_...:123456)");
      return;
    }

    setLoading(true);
    try {
      saveConnection();
      const res = await mobileClient.pairWithQR(payloadToUse, deviceName);
      if (res && (res.access_token || res.token || res.status === 'paired')) {
        setIsPaired(true);
        Alert.alert("✓ QR Paired Successfully", `Device '${deviceName}' authenticated via QR Code!`);
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
      Alert.alert("Pairing Error", "Please enter the 6-digit PIN displayed on your desktop JARVIS OS screen.");
      return;
    }

    setLoading(true);
    try {
      saveConnection();
      const res = await mobileClient.easyPair(pin.trim(), deviceName);
      if (res && (res.token || res.status === 'paired')) {
        setIsPaired(true);
        Alert.alert("✓ Paired Successfully", `Device '${deviceName}' paired with JARVIS OS!`);
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
      <Text style={styles.headerTitle}>SECURE DEVICE PAIRING</Text>

      {/* ── SERVER CONNECTION SETTINGS ── */}
      <View style={styles.sectionCard}>
        <Text style={styles.cardTitle}>🌐 DESKTOP SERVER IP & PORT</Text>
        <Text style={styles.cardSub}>Ensure your phone and laptop are on the same Wi-Fi network</Text>

        <View style={styles.row}>
          <View style={{ flex: 3, marginRight: 8 }}>
            <Text style={styles.label}>Laptop Wi-Fi IP:</Text>
            <TextInput
              style={styles.input}
              value={host}
              onChangeText={setHost}
              placeholder="10.200.40.177"
              placeholderTextColor="#557090"
            />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.label}>Port:</Text>
            <TextInput
              style={styles.input}
              value={port}
              onChangeText={setPort}
              keyboardType="numeric"
              placeholder="8000"
              placeholderTextColor="#557090"
            />
          </View>
        </View>

        <TouchableOpacity style={styles.saveBtn} onPress={saveConnection}>
          <Text style={styles.saveBtnText}>💾 SAVE SERVER IP</Text>
        </TouchableOpacity>
      </View>

      {/* ── QR CODE PAIRING ── */}
      <View style={styles.sectionCard}>
        <Text style={styles.cardTitle}>📷 PAIR WITH QR CODE PAYLOAD</Text>
        <Text style={styles.cardSub}>Scan or paste the QR pairing payload from your desktop screen</Text>

        <Text style={styles.label}>QR Code Payload:</Text>
        <TextInput
          style={styles.input}
          value={qrPayload}
          onChangeText={setQrPayload}
          placeholder="jarvis_pair://sess_123:849201"
          placeholderTextColor="#557090"
        />

        <TouchableOpacity style={styles.secondaryBtn} onPress={() => handleQRPairing()} disabled={loading}>
          <Text style={styles.secondaryBtnText}>{loading ? "AUTHENTICATING..." : "📱 PAIR WITH QR CODE NOW"}</Text>
        </TouchableOpacity>
      </View>

      {/* ── 6-DIGIT DESKTOP PIN PAIRING ── */}
      <View style={styles.sectionCard}>
        <Text style={styles.cardTitle}>🔑 PAIR WITH 6-DIGIT DESKTOP PIN</Text>
        <Text style={styles.cardSub}>Enter 6-digit PIN shown on desktop screen to generate signed JWT key</Text>

        <Text style={styles.label}>Device Name:</Text>
        <TextInput
          style={styles.input}
          value={deviceName}
          onChangeText={setDeviceName}
        />

        <Text style={styles.label}>6-Digit Pairing PIN:</Text>
        <TextInput
          style={[styles.input, styles.pinInput]}
          value={pin}
          onChangeText={setPin}
          keyboardType="numeric"
          maxLength={6}
          placeholder="e.g. 121706"
          placeholderTextColor="#557090"
        />

        <TouchableOpacity style={styles.primaryBtn} onPress={handlePairing} disabled={loading}>
          <Text style={styles.btnText}>{loading ? "PAIRING..." : "🔒 PAIR DEVICE NOW"}</Text>
        </TouchableOpacity>

        {isPaired && (
          <View style={styles.successBadge}>
            <Text style={styles.successText}>✓ DEVICE TRUSTED & CONNECTED</Text>
          </View>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#050d08', padding: 16 },
  headerTitle: { color: '#00ff66', fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace', marginBottom: 16 },
  sectionCard: { backgroundColor: '#0a1a0f', padding: 16, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.2)', marginBottom: 16 },
  cardTitle: { color: '#ffffff', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace' },
  cardSub: { color: '#668877', fontSize: 11, marginTop: 4, marginBottom: 12, fontFamily: 'monospace' },
  row: { flexDirection: 'row', alignItems: 'center' },
  label: { color: '#00ff66', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace', marginTop: 8, marginBottom: 4 },
  input: { backgroundColor: '#050d08', color: '#ffffff', borderRadius: 8, padding: 10, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.3)', fontFamily: 'monospace' },
  pinInput: { fontSize: 22, letterSpacing: 6, textAlign: 'center', fontWeight: 'bold', color: '#00ff66' },
  saveBtn: { backgroundColor: 'rgba(0, 229, 255, 0.15)', borderWidth: 1, borderColor: '#00e5ff', padding: 10, borderRadius: 8, alignItems: 'center', marginTop: 12 },
  saveBtnText: { color: '#00e5ff', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  primaryBtn: { backgroundColor: '#00cc52', padding: 14, borderRadius: 10, alignItems: 'center', marginTop: 16 },
  btnText: { color: '#ffffff', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace' },
  secondaryBtn: { backgroundColor: 'rgba(0, 255, 102, 0.15)', borderWidth: 1, borderColor: '#00ff66', padding: 12, borderRadius: 8, alignItems: 'center', marginTop: 12 },
  secondaryBtnText: { color: '#00ff66', fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' },
  successBadge: { backgroundColor: 'rgba(0, 255, 102, 0.2)', borderWidth: 1, borderColor: '#00ff66', padding: 10, borderRadius: 8, marginTop: 14, alignItems: 'center' },
  successText: { color: '#00ff66', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' }
});

