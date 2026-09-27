import React, { useState } from 'react';
import {
  View,
  TextInput,
  TouchableOpacity,
  StyleSheet
} from 'react-native';
import { Mic, Send } from 'lucide-react-native';

interface CommandInputPillProps {
  isListening?: boolean;
  onToggleListening?: () => void;
  onSubmitText?: (text: string) => void;
}

export const CommandInputPill: React.FC<CommandInputPillProps> = ({
  isListening = false,
  onToggleListening,
  onSubmitText
}) => {
  const [inputText, setInputText] = useState('');

  const handleSend = () => {
    const trimmed = inputText.trim();
    if (!trimmed) return;
    if (onSubmitText) onSubmitText(trimmed);
    setInputText('');
  };

  return (
    <View style={styles.pillContainer}>
      {/* Left Mic Button */}
      <TouchableOpacity
        activeOpacity={0.8}
        onPress={onToggleListening}
        style={[
          styles.micButton,
          isListening && styles.micButtonActive
        ]}
      >
        <Mic
          size={18}
          color={isListening ? '#00e5ff' : '#94a3b8'}
        />
      </TouchableOpacity>

      {/* Input Field */}
      <TextInput
        value={inputText}
        onChangeText={setInputText}
        placeholder="Tap to speak..."
        placeholderTextColor="#64748b"
        style={styles.textInput}
        onSubmitEditing={handleSend}
        returnKeyType="send"
      />

      {/* Right Send Button */}
      <TouchableOpacity
        activeOpacity={0.8}
        onPress={handleSend}
        style={[
          styles.sendButton,
          inputText.trim().length > 0 && styles.sendButtonActive
        ]}
      >
        <Send
          size={16}
          color="#ffffff"
        />
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  pillContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(10, 15, 29, 0.75)',
    borderWidth: 1.2,
    borderColor: 'rgba(59, 130, 246, 0.35)',
    borderRadius: 30,
    marginHorizontal: 18,
    marginVertical: 10,
    paddingVertical: 5,
    paddingHorizontal: 6,
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 10,
    elevation: 4
  },
  micButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: 'rgba(30, 41, 59, 0.6)',
    alignItems: 'center',
    justifyContent: 'center'
  },
  micButtonActive: {
    backgroundColor: 'rgba(0, 229, 255, 0.2)',
    borderWidth: 1,
    borderColor: '#00e5ff'
  },
  textInput: {
    flex: 1,
    color: '#ffffff',
    fontSize: 14,
    paddingHorizontal: 12,
    paddingVertical: 6
  },
  sendButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#2563eb',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#2563eb',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.6,
    shadowRadius: 8
  },
  sendButtonActive: {
    backgroundColor: '#00e5ff',
    shadowColor: '#00e5ff'
  }
});
