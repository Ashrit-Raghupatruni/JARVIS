import React, { useState } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, Alert, ScrollView } from 'react-native';
import { mobileClient } from '../api/client';

export default function PairingScreen() {
  const [host, setHost] = useState('192.168.1.100');
  const [port, setPort] = useState('8000');
  const [pin, setPin] = useState('');
  const [deviceName, setDeviceName] = useState('Android Phone');
  const [isPaired, setIsPaired] = useState(false);
  const [loading, setLoading] = useState(false);

  const saveConnection = () => {
    const portNum = parseInt(port, 10) || 8000;
    mobileClient.setServerAddress(host, portNum);
    Alert.alert("Server Configured", `Updated server address to http://${host}:${portNum}`);
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

      <View style={styles.sectionCard}>
        <Text style={styles.cardTitle}>🌐 DESKTOP SERVER CONFIGURATION</Text>
        <Text style={styles.label}>Desktop Local IP Address:</Text>
        <TextInput
          style={styles.input}
          value={host}
          onChangeText={setHost}
          placeholder="e.g. 192.168.1.100"
          placeholderTextColor="#557090"
        />

        <Text style={styles.label}>Port:</Text>
        <TextInput
          style={styles.input}
          value={port}
          onChangeText={setPort}
          keyboardType="numeric"
          placeholder="8000"
          placeholderTextColor="#557090"
        />

        <TouchableOpacity style={styles.secondaryBtn} onPress={saveConnection}>
          <Text style={styles.secondaryBtnText}>SAVE SERVER ADDRESS</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.sectionCard}>
        <Text style={styles.cardTitle}>🔑 PAIR WITH 6-DIGIT DESKTOP PIN</Text>
        <Text style={styles.cardSub}>Enter 6-digit PIN shown on desktop screen to generate signed Ed25519 / JWT key</Text>

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
          placeholder="e.g. 849201"
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
  label: { color: '#00ff66', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace', marginTop: 10, marginBottom: 4 },
  input: { backgroundColor: '#050d08', color: '#ffffff', borderRadius: 8, padding: 10, borderWidth: 1, borderColor: 'rgba(0, 255, 102, 0.3)', fontFamily: 'monospace' },
  pinInput: { fontSize: 20, letterSpacing: 6, textAlign: 'center', fontWeight: 'bold' },
  primaryBtn: { backgroundColor: '#00cc52', padding: 14, borderRadius: 10, alignItems: 'center', marginTop: 16 },
  btnText: { color: '#ffffff', fontSize: 13, fontWeight: 'bold', fontFamily: 'monospace' },
  secondaryBtn: { backgroundColor: 'rgba(0, 255, 102, 0.15)', borderWidth: 1, borderColor: '#00ff66', padding: 10, borderRadius: 8, alignItems: 'center', marginTop: 12 },
  secondaryBtnText: { color: '#00ff66', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' },
  successBadge: { backgroundColor: 'rgba(0, 255, 102, 0.2)', borderWidth: 1, borderColor: '#00ff66', padding: 10, borderRadius: 8, marginTop: 14, alignItems: 'center' },
  successText: { color: '#00ff66', fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' }
});
