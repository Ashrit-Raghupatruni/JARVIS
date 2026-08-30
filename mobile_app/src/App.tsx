import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  StatusBar
} from 'react-native';

import DashboardScreen from './screens/DashboardScreen';
import ControlScreen from './screens/ControlScreen';
import ApprovalsScreen from './screens/ApprovalsScreen';
import ChatScreen from './screens/ChatScreen';
import FileExplorerScreen from './screens/FileExplorerScreen';
import PairingScreen from './screens/PairingScreen';
import { mobileClient } from './api/client';

type TabType = 'dashboard' | 'control' | 'chat' | 'approvals' | 'files' | 'pairing';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');

  const renderActiveScreen = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardScreen />;
      case 'control':
        return <ControlScreen />;
      case 'chat':
        return <ChatScreen />;
      case 'approvals':
        return <ApprovalsScreen />;
      case 'files':
        return <FileExplorerScreen />;
      case 'pairing':
        return <PairingScreen />;
      default:
        return <DashboardScreen />;
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#030712" />

      {/* Top HUD Header Bar */}
      <View style={styles.topHeader}>
        <View style={styles.brandGroup}>
          <View style={styles.arcReactorCircle}>
            <View style={styles.arcReactorInner} />
          </View>
          <View>
            <Text style={styles.brandTitle}>J.A.R.V.I.S.</Text>
            <Text style={styles.brandSub}>MOBILE TACTICAL COMPANION</Text>
          </View>
        </View>

        <TouchableOpacity
          style={styles.hostPill}
          onPress={() => setActiveTab('pairing')}
        >
          <View style={styles.pulseDot} />
          <Text style={styles.hostText}>{mobileClient.getHost()}:{mobileClient.getPort()}</Text>
        </TouchableOpacity>
      </View>

      {/* Main Active Screen Container */}
      <View style={styles.screenContainer}>
        {renderActiveScreen()}
      </View>

      {/* Ergonomic Bottom Navigation Bar */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'dashboard' && styles.activeTabItem]}
          onPress={() => setActiveTab('dashboard')}
        >
          <Text style={styles.tabIcon}>📊</Text>
          <Text style={[styles.tabLabel, activeTab === 'dashboard' && styles.activeTabLabel]}>HUD</Text>
          {activeTab === 'dashboard' && <View style={styles.activeGlowBar} />}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'control' && styles.activeTabItem]}
          onPress={() => setActiveTab('control')}
        >
          <Text style={styles.tabIcon}>⚡</Text>
          <Text style={[styles.tabLabel, activeTab === 'control' && styles.activeTabLabel]}>ACTIONS</Text>
          {activeTab === 'control' && <View style={styles.activeGlowBar} />}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'chat' && styles.activeTabItem]}
          onPress={() => setActiveTab('chat')}
        >
          <Text style={styles.tabIcon}>💬</Text>
          <Text style={[styles.tabLabel, activeTab === 'chat' && styles.activeTabLabel]}>CHAT</Text>
          {activeTab === 'chat' && <View style={styles.activeGlowBar} />}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'approvals' && styles.activeTabItem]}
          onPress={() => setActiveTab('approvals')}
        >
          <Text style={styles.tabIcon}>🛡️</Text>
          <Text style={[styles.tabLabel, activeTab === 'approvals' && styles.activeTabLabel]}>GATE</Text>
          {activeTab === 'approvals' && <View style={styles.activeGlowBar} />}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'files' && styles.activeTabItem]}
          onPress={() => setActiveTab('files')}
        >
          <Text style={styles.tabIcon}>📁</Text>
          <Text style={[styles.tabLabel, activeTab === 'files' && styles.activeTabLabel]}>FILES</Text>
          {activeTab === 'files' && <View style={styles.activeGlowBar} />}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'pairing' && styles.activeTabItem]}
          onPress={() => setActiveTab('pairing')}
        >
          <Text style={styles.tabIcon}>📡</Text>
          <Text style={[styles.tabLabel, activeTab === 'pairing' && styles.activeTabLabel]}>NETWORK</Text>
          {activeTab === 'pairing' && <View style={styles.activeGlowBar} />}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#030712' },
  topHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#0b1329',
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b'
  },
  brandGroup: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  arcReactorCircle: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#00e5ff',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#030712'
  },
  arcReactorInner: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#00e5ff'
  },
  brandTitle: {
    color: '#f8fafc',
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    letterSpacing: 2
  },
  brandSub: {
    color: '#64748b',
    fontSize: 8,
    fontWeight: 'bold',
    fontFamily: 'monospace'
  },
  hostPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#030712',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155'
  },
  pulseDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#10b981'
  },
  hostText: {
    color: '#94a3b8',
    fontSize: 9,
    fontFamily: 'monospace'
  },
  screenContainer: { flex: 1 },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#0b1329',
    borderTopWidth: 1,
    borderTopColor: '#1e293b',
    paddingVertical: 8,
    paddingHorizontal: 6,
    justifyContent: 'space-around'
  },
  tabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 4,
    position: 'relative'
  },
  activeTabItem: {
    borderRadius: 8
  },
  tabIcon: {
    fontSize: 17,
    marginBottom: 3
  },
  tabLabel: {
    color: '#64748b',
    fontSize: 8.5,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    letterSpacing: 0.5
  },
  activeTabLabel: {
    color: '#00e5ff'
  },
  activeGlowBar: {
    position: 'absolute',
    bottom: -6,
    width: 20,
    height: 2.5,
    borderRadius: 1.5,
    backgroundColor: '#00e5ff'
  }
});

