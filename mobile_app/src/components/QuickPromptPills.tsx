import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView
} from 'react-native';
import { BookOpen, FileText, LayoutGrid } from 'lucide-react-native';

interface QuickPromptPillsProps {
  onSelectPrompt?: (prompt: string) => void;
}

export const QuickPromptPills: React.FC<QuickPromptPillsProps> = ({
  onSelectPrompt
}) => {
  const prompts = [
    { label: 'Explain this', icon: BookOpen, query: 'Explain the active screen content' },
    { label: 'Summarize', icon: FileText, query: 'Summarize this document' },
    { label: 'Open app', icon: LayoutGrid, query: 'Open application' }
  ];

  return (
    <View style={styles.container}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {prompts.map((item, index) => {
          const Icon = item.icon;
          return (
            <TouchableOpacity
              key={index}
              activeOpacity={0.75}
              onPress={() => onSelectPrompt && onSelectPrompt(item.query)}
              style={styles.pill}
            >
              <Icon size={14} color="#00e5ff" style={styles.pillIcon} />
              <Text style={styles.pillText}>{item.label}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginVertical: 6,
    paddingHorizontal: 18
  },
  scrollContent: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center'
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(15, 23, 42, 0.7)',
    borderWidth: 1,
    borderColor: 'rgba(59, 130, 246, 0.3)',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.15,
    shadowRadius: 4
  },
  pillIcon: {
    marginRight: 6
  },
  pillText: {
    color: '#e2e8f0',
    fontSize: 12,
    fontWeight: '500'
  }
});
