import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet
} from 'react-native';
import {
  Home,
  MessageSquare,
  Mic,
  LayoutGrid,
  User
} from 'lucide-react-native';

export type MobileTab = 'home' | 'chat' | 'apps' | 'files' | 'approvals' | 'profile';

interface FloatingBottomDockProps {
  activeTab: MobileTab;
  onSelectTab: (tab: MobileTab) => void;
  onPressMic: () => void;
  isListening?: boolean;
}

export const FloatingBottomDock: React.FC<FloatingBottomDockProps> = ({
  activeTab,
  onSelectTab,
  onPressMic,
  isListening = false
}) => {
  return (
    <View style={styles.dockWrapper}>
      <View style={styles.dockBar}>
        {/* Tab 1: Home */}
        <TouchableOpacity
          activeOpacity={0.7}
          onPress={() => onSelectTab('home')}
          style={[styles.dockItem, activeTab === 'home' && styles.activePill]}
        >
          <Home
            size={18}
            color={activeTab === 'home' ? '#00e5ff' : '#64748b'}
          />
          <Text
            style={[
              styles.dockLabel,
              activeTab === 'home' && styles.activeDockLabel
            ]}
          >
            Home
          </Text>
        </TouchableOpacity>

        {/* Tab 2: Chat */}
        <TouchableOpacity
          activeOpacity={0.7}
          onPress={() => onSelectTab('chat')}
          style={[styles.dockItem, activeTab === 'chat' && styles.activePill]}
        >
          <MessageSquare
            size={18}
            color={activeTab === 'chat' ? '#00e5ff' : '#64748b'}
          />
          <Text
            style={[
              styles.dockLabel,
              activeTab === 'chat' && styles.activeDockLabel
            ]}
          >
            Chat
          </Text>
        </TouchableOpacity>

        {/* Center Elevated Floating Microphone Orb */}
        <View style={styles.centerMicWrapper}>
          {/* Outer Cyan Shockwave Ring */}
          <View style={styles.shockwaveRing} />
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={onPressMic}
            style={[
              styles.centerMicOrb,
              isListening && styles.centerMicOrbActive
            ]}
          >
            <Mic
              size={24}
              color="#ffffff"
            />
          </TouchableOpacity>
        </View>

        {/* Tab 3: Apps */}
        <TouchableOpacity
          activeOpacity={0.7}
          onPress={() => onSelectTab('apps')}
          style={[styles.dockItem, activeTab === 'apps' && styles.activePill]}
        >
          <LayoutGrid
            size={18}
            color={activeTab === 'apps' ? '#00e5ff' : '#64748b'}
          />
          <Text
            style={[
              styles.dockLabel,
              activeTab === 'apps' && styles.activeDockLabel
            ]}
          >
            Apps
          </Text>
        </TouchableOpacity>

        {/* Tab 4: Profile */}
        <TouchableOpacity
          activeOpacity={0.7}
          onPress={() => onSelectTab('profile')}
          style={[styles.dockItem, activeTab === 'profile' && styles.activePill]}
        >
          <User
            size={18}
            color={activeTab === 'profile' ? '#00e5ff' : '#64748b'}
          />
          <Text
            style={[
              styles.dockLabel,
              activeTab === 'profile' && styles.activeDockLabel
            ]}
          >
            Profile
          </Text>
        </TouchableOpacity>
      </View>

      {/* iOS Home Indicator Bar */}
      <View style={styles.homeIndicator} />
    </View>
  );
};

const styles = StyleSheet.create({
  dockWrapper: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(2, 6, 23, 0.92)',
    borderTopWidth: 1,
    borderTopColor: 'rgba(59, 130, 246, 0.25)',
    paddingTop: 8,
    paddingBottom: 6,
    alignItems: 'center',
    zIndex: 50
  },
  dockBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    width: '100%',
    paddingHorizontal: 12
  },
  dockItem: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 20
  },
  activePill: {
    backgroundColor: 'rgba(37, 99, 235, 0.35)',
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.6)',
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.4,
    shadowRadius: 8
  },
  dockLabel: {
    color: '#64748b',
    fontSize: 10,
    fontWeight: '500',
    marginTop: 2
  },
  activeDockLabel: {
    color: '#ffffff',
    fontWeight: '700'
  },
  centerMicWrapper: {
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: -22
  },
  shockwaveRing: {
    position: 'absolute',
    width: 68,
    height: 68,
    borderRadius: 34,
    borderWidth: 1.5,
    borderColor: 'rgba(0, 229, 255, 0.35)',
    backgroundColor: 'rgba(0, 229, 255, 0.08)'
  },
  centerMicOrb: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: '#0284c7',
    borderWidth: 2,
    borderColor: '#00e5ff',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 14,
    elevation: 8
  },
  centerMicOrbActive: {
    backgroundColor: '#00e5ff',
    shadowColor: '#00e5ff',
    shadowOpacity: 1,
    shadowRadius: 20
  },
  homeIndicator: {
    width: 134,
    height: 4,
    backgroundColor: '#ffffff',
    borderRadius: 2,
    opacity: 0.5,
    marginTop: 8
  }
});
