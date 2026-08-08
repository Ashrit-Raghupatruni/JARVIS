import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, SafeAreaView, StatusBar } from 'react-native';

import DashboardScreen from './screens/DashboardScreen';
import ControlScreen from './screens/ControlScreen';
import ApprovalsScreen from './screens/ApprovalsScreen';
import ChatScreen from './screens/ChatScreen';
import FileExplorerScreen from './screens/FileExplorerScreen';
import PairingScreen from './screens/PairingScreen';

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
      <StatusBar barStyle="light-content" backgroundColor="#050d08" />

      {/* Top Header Bar */}
      <View style={styles.topHeader}>
        <Text style={styles.brandTitle}>JARVIS OS</Text>
        <Text style={styles.brandSub}>MOBILE COMPANION</Text>
      </View>

      {/* Screen Container */}
      <View style={styles.screenContainer}>
        {renderActiveScreen()}
      </View>

      {/* Bottom Navigation Bar */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'dashboard' && styles.activeTabItem]}
          onPress={() => setActiveTab('dashboard')}
        >
          <Text style={[styles.tabIcon, activeTab === 'dashboard' && styles.activeTabIcon]}>📊</Text>
          <Text style={[styles.tabLabel, activeTab === 'dashboard' && styles.activeTabLabel]}>HUD</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'control' && styles.activeTabItem]}
          onPress={() => setActiveTab('control')}
        >
          <Text style={[styles.tabIcon, activeTab === 'control' && styles.activeTabIcon]}>⚡</Text>
          <Text style={[styles.tabLabel, activeTab === 'control' && styles.activeTabLabel]}>CONTROL</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'chat' && styles.activeTabItem]}
          onPress={() => setActiveTab('chat')}
        >
          <Text style={[styles.tabIcon, activeTab === 'chat' && styles.activeTabIcon]}>💬</Text>
          <Text style={[styles.tabLabel, activeTab === 'chat' && styles.activeTabLabel]}>CHAT</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'approvals' && styles.activeTabItem]}
          onPress={() => setActiveTab('approvals')}
        >
          <Text style={[styles.tabIcon, activeTab === 'approvals' && styles.activeTabIcon]}>🛡️</Text>
          <Text style={[styles.tabLabel, activeTab === 'approvals' && styles.activeTabLabel]}>GATE</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'files' && styles.activeTabItem]}
          onPress={() => setActiveTab('files')}
        >
          <Text style={[styles.tabIcon, activeTab === 'files' && styles.activeTabIcon]}>📁</Text>
          <Text style={[styles.tabLabel, activeTab === 'files' && styles.activeTabLabel]}>FILES</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === 'pairing' && styles.activeTabItem]}
          onPress={() => setActiveTab('pairing')}
        >
          <Text style={[styles.tabIcon, activeTab === 'pairing' && styles.activeTabIcon]}>🔒</Text>
          <Text style={[styles.tabLabel, activeTab === 'pairing' && styles.activeTabLabel]}>PAIR</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#050d08' },
  topHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, backgroundColor: '#0a1a0f', borderBottomWidth: 1, borderBottomColor: 'rgba(0, 255, 102, 0.2)' },
  brandTitle: { color: '#00ff66', fontSize: 14, fontWeight: 'bold', fontFamily: 'monospace', letterSpacing: 1.5 },
  brandSub: { color: '#668877', fontSize: 9, fontWeight: 'bold', fontFamily: 'monospace' },
  screenContainer: { flex: 1 },
  tabBar: { flexDirection: 'row', backgroundColor: '#0a1a0f', borderTopWidth: 1, borderTopColor: 'rgba(0, 255, 102, 0.2)', paddingVertical: 6, paddingHorizontal: 4 },
  tabItem: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 4, borderRadius: 8 },
  activeTabItem: { backgroundColor: 'rgba(0, 255, 102, 0.15)' },
  tabIcon: { fontSize: 16, marginBottom: 2 },
  activeTabIcon: { transform: [{ scale: 1.1 }] },
  tabLabel: { color: '#557090', fontSize: 8, fontWeight: 'bold', fontFamily: 'monospace' },
  activeTabLabel: { color: '#00ff66' }
});
