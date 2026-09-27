import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity
} from 'react-native';
import { Bell, Settings } from 'lucide-react-native';

interface HeaderGreetingProps {
  userName?: string;
  hasUnreadNotification?: boolean;
  onPressNotification?: () => void;
  onPressSettings?: () => void;
}

export const HeaderGreeting: React.FC<HeaderGreetingProps> = ({
  userName = 'Ashrit',
  hasUnreadNotification = true,
  onPressNotification,
  onPressSettings
}) => {
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning,';
    if (hour < 17) return 'Good Afternoon,';
    return 'Good Evening,';
  };

  return (
    <View style={styles.headerContainer}>
      {/* Left: Avatar + Greeting + Subtitle */}
      <View style={styles.leftGroup}>
        {/* User Circular Avatar */}
        <View style={styles.avatarCircle}>
          <Text style={styles.avatarInitial}>{userName.charAt(0).toUpperCase()}</Text>
        </View>

        <View style={styles.textGroup}>
          <Text style={styles.greetingText}>{getGreeting()}</Text>
          <Text style={styles.userNameText}>{userName}</Text>
          <Text style={styles.subtitleText}>Let's make today productive.</Text>
        </View>
      </View>

      {/* Right: Notification Bell & Settings */}
      <View style={styles.rightGroup}>
        <TouchableOpacity
          activeOpacity={0.7}
          onPress={onPressNotification}
          style={styles.iconButton}
        >
          <Bell size={20} color="#cbd5e1" />
          {hasUnreadNotification && <View style={styles.notificationDot} />}
        </TouchableOpacity>

        <TouchableOpacity
          activeOpacity={0.7}
          onPress={onPressSettings}
          style={styles.iconButton}
        >
          <Settings size={20} color="#cbd5e1" />
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  headerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 18,
    paddingTop: 10,
    paddingBottom: 6
  },
  leftGroup: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12
  },
  avatarCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(30, 41, 59, 0.7)',
    borderWidth: 1.5,
    borderColor: 'rgba(59, 130, 246, 0.35)',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.25,
    shadowRadius: 8
  },
  avatarInitial: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '700'
  },
  textGroup: {
    flexDirection: 'column'
  },
  greetingText: {
    color: '#94a3b8',
    fontSize: 12,
    fontWeight: '400',
    letterSpacing: 0.3
  },
  userNameText: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '800',
    letterSpacing: 0.2,
    marginTop: -1
  },
  subtitleText: {
    color: '#64748b',
    fontSize: 10.5,
    fontStyle: 'italic',
    marginTop: 1
  },
  rightGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10
  },
  iconButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: 'rgba(15, 23, 42, 0.65)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative'
  },
  notificationDot: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: '#00e5ff',
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 4
  }
});
