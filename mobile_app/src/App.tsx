import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  SafeAreaView,
  StatusBar
} from 'react-native';

import { SleekHomeScreen } from './screens/SleekHomeScreen';
import ControlScreen from './screens/ControlScreen';
import ApprovalsScreen from './screens/ApprovalsScreen';
import ChatScreen from './screens/ChatScreen';
import FileExplorerScreen from './screens/FileExplorerScreen';
import PairingScreen from './screens/PairingScreen';
import { FloatingBottomDock, MobileTab } from './components/FloatingBottomDock';
import { mobileClient } from './api/client';

export default function App() {
  const [activeTab, setActiveTab] = useState<MobileTab>('home');
  const [isListening, setIsListening] = useState(false);

  const handleToggleMic = () => {
    const nextState = !isListening;
    setIsListening(nextState);
    if (nextState) {
      mobileClient.sendWebSocketMessage({
        type: 'voice_start',
        timestamp: new Date().toISOString()
      });
    } else {
      mobileClient.sendWebSocketMessage({
        type: 'voice_stop',
        timestamp: new Date().toISOString()
      });
    }
  };

  const renderActiveScreen = () => {
    switch (activeTab) {
      case 'home':
        return <SleekHomeScreen onNavigateTab={(tab) => {
          if (tab === 'chat' || tab === 'apps' || tab === 'profile') {
            setActiveTab(tab as MobileTab);
          } else if (tab === 'control') {
            setActiveTab('apps');
          } else if (tab === 'pairing') {
            setActiveTab('profile');
          }
        }} />;
      case 'chat':
        return <ChatScreen />;
      case 'apps':
        return <ControlScreen />;
      case 'profile':
        return <PairingScreen />;
      default:
        return <SleekHomeScreen />;
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#02040a" />

      {/* Main Active Screen Container */}
      <View style={styles.screenContainer}>
        {renderActiveScreen()}
      </View>

      {/* Sleek Minimalist Floating Bottom Dock with Center Elevated Mic */}
      <FloatingBottomDock
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onPressMic={handleToggleMic}
        isListening={isListening}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#02040a'
  },
  screenContainer: {
    flex: 1,
    backgroundColor: '#02040a'
  }
});
