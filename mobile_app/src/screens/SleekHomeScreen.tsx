import React, { useEffect, useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Alert
} from 'react-native';
import { HeaderGreeting } from '../components/HeaderGreeting';
import { JarvisMobileCoreOrb } from '../components/JarvisMobileCoreOrb';
import { CommandInputPill } from '../components/CommandInputPill';
import { QuickPromptPills } from '../components/QuickPromptPills';
import { QuickActionsBentoGrid } from '../components/QuickActionsBentoGrid';
import { mobileClient, SystemTelemetryData } from '../api/client';

interface SleekHomeScreenProps {
  onNavigateTab?: (tab: string) => void;
}

export const SleekHomeScreen: React.FC<SleekHomeScreenProps> = ({ onNavigateTab }) => {
  const [isListening, setIsListening] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0.45);
  const [telemetry, setTelemetry] = useState<SystemTelemetryData | null>(null);

  useEffect(() => {
    mobileClient.connectWebSocket(
      (data) => {
        setTelemetry(data);
      },
      (msg) => {
        if (msg.type === 'chat_response') {
          if (msg.status === 'completed') {
            setIsListening(false);
          }
        }
      }
    );
  }, []);

  const handleToggleListening = () => {
    const next = !isListening;
    setIsListening(next);
    if (next) {
      setAudioLevel(0.8);
    } else {
      setAudioLevel(0.2);
    }
  };

  const handleSendPrompt = (prompt: string) => {
    setIsListening(true);
    mobileClient.sendWebSocketMessage({
      type: 'chat',
      text: prompt,
      timestamp: new Date().toISOString()
    });
  };

  const handleQuickAction = async (actionId: string) => {
    switch (actionId) {
      case 'control_pc':
        if (onNavigateTab) onNavigateTab('control');
        break;

      case 'files':
        if (onNavigateTab) onNavigateTab('files');
        break;

      case 'camera':
        Alert.alert('Camera Perception', 'Scanning desktop viewport and environment...');
        break;

      case 'tasks':
        if (onNavigateTab) onNavigateTab('approvals');
        break;

      case 'get_insights':
        handleSendPrompt('Provide today\'s intelligence briefing and system insights');
        break;

      case 'search_web':
        handleSendPrompt('Search web for latest AI OS updates');
        break;

      case 'my_schedule':
        handleSendPrompt('What is my schedule for today?');
        break;

      case 'more':
        if (onNavigateTab) onNavigateTab('apps');
        break;

      default:
        break;
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Header Greeting */}
        <HeaderGreeting
          userName="Ashrit"
          hasUnreadNotification={Boolean(telemetry && telemetry.battery_percent !== undefined && telemetry.battery_percent <= 20)}
          onPressNotification={() => {
            const bat = telemetry?.battery_percent !== undefined ? `${telemetry.battery_percent}%` : 'Unavailable';
            const cpu = telemetry?.cpu_percent !== undefined ? `${telemetry.cpu_percent}%` : 'Unavailable';
            const ram = telemetry?.ram_percent !== undefined ? `${telemetry.ram_percent}%` : 'Unavailable';
            Alert.alert(
              'System Telemetry',
              `Host Status: Online\nBattery: ${bat}\nCPU Load: ${cpu}\nRAM Usage: ${ram}`
            );
          }}
          onPressSettings={() => onNavigateTab && onNavigateTab('pairing')}
        />

        {/* Central Luminous JARVIS Core Orb */}
        <JarvisMobileCoreOrb
          isListening={isListening}
          audioLevel={audioLevel}
          onPress={handleToggleListening}
        />

        {/* Floating Command Bar Input Pill */}
        <CommandInputPill
          isListening={isListening}
          onToggleListening={handleToggleListening}
          onSubmitText={handleSendPrompt}
        />

        {/* Horizontal Quick Prompt Chips */}
        <QuickPromptPills
          onSelectPrompt={handleSendPrompt}
        />

        {/* 2x4 Bento Grid of Glass Action Cards */}
        <QuickActionsBentoGrid
          onActionPress={handleQuickAction}
        />

        {/* Bottom spacing to ensure content clears floating dock */}
        <View style={styles.bottomSpacer} />
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#030712'
  },
  scrollContent: {
    paddingBottom: 90
  },
  bottomSpacer: {
    height: 30
  }
});
