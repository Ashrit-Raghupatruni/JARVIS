import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet
} from 'react-native';
import {
  Laptop,
  FileText,
  Camera,
  CheckSquare,
  Lightbulb,
  Globe,
  Calendar,
  LayoutGrid
} from 'lucide-react-native';

interface QuickActionsBentoGridProps {
  onActionPress?: (actionId: string) => void;
}

export const QuickActionsBentoGrid: React.FC<QuickActionsBentoGridProps> = ({
  onActionPress
}) => {
  const actions = [
    { id: 'control_pc', label: 'Control PC', icon: Laptop, color: '#38bdf8' },
    { id: 'files', label: 'Files', icon: FileText, color: '#a78bfa' },
    { id: 'camera', label: 'Camera', icon: Camera, color: '#2dd4bf' },
    { id: 'tasks', label: 'Tasks', icon: CheckSquare, color: '#34d399' },
    { id: 'get_insights', label: 'Get Insights', icon: Lightbulb, color: '#fbbf24' },
    { id: 'search_web', label: 'Search Web', icon: Globe, color: '#60a5fa' },
    { id: 'my_schedule', label: 'My Schedule', icon: Calendar, color: '#f472b6' },
    { id: 'more', label: 'More', icon: LayoutGrid, color: '#94a3b8' }
  ];

  return (
    <View style={styles.gridContainer}>
      {actions.map((item) => {
        const Icon = item.icon;
        return (
          <TouchableOpacity
            key={item.id}
            activeOpacity={0.7}
            onPress={() => onActionPress && onActionPress(item.id)}
            style={styles.card}
          >
            <View style={styles.iconWrapper}>
              <Icon size={20} color={item.color} />
            </View>
            <Text style={styles.cardLabel}>{item.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
};

const styles = StyleSheet.create({
  gridContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    paddingHorizontal: 18,
    marginVertical: 8,
    rowGap: 10
  },
  card: {
    width: '23%',
    aspectRatio: 0.95,
    backgroundColor: 'rgba(15, 23, 42, 0.65)',
    borderWidth: 1,
    borderColor: 'rgba(59, 130, 246, 0.22)',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    paddingHorizontal: 4,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 3
  },
  iconWrapper: {
    marginBottom: 6,
    alignItems: 'center',
    justifyContent: 'center'
  },
  cardLabel: {
    color: '#cbd5e1',
    fontSize: 9.5,
    fontWeight: '500',
    textAlign: 'center',
    letterSpacing: 0.2
  }
});
