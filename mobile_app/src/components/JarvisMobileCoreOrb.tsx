import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  TouchableOpacity,
  Easing
} from 'react-native';

interface JarvisMobileCoreOrbProps {
  isListening?: boolean;
  audioLevel?: number;
  onPress?: () => void;
}

export const JarvisMobileCoreOrb: React.FC<JarvisMobileCoreOrbProps> = ({
  isListening = false,
  audioLevel = 0.4,
  onPress
}) => {
  const rotateAnim1 = useRef(new Animated.Value(0)).current;
  const rotateAnim2 = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const waveHeightAnim = useRef(new Animated.Value(6)).current;

  // Continuous orbital ring rotations
  useEffect(() => {
    const loop1 = Animated.loop(
      Animated.timing(rotateAnim1, {
        toValue: 1,
        duration: 18000,
        easing: Easing.linear,
        useNativeDriver: true
      })
    );

    const loop2 = Animated.loop(
      Animated.timing(rotateAnim2, {
        toValue: 1,
        duration: 28000,
        easing: Easing.linear,
        useNativeDriver: true
      })
    );

    loop1.start();
    loop2.start();

    return () => {
      loop1.stop();
      loop2.stop();
    };
  }, [rotateAnim1, rotateAnim2]);

  // Audio reactivity & pulse
  useEffect(() => {
    if (isListening) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.08,
            duration: 800,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true
          }),
          Animated.timing(pulseAnim, {
            toValue: 0.98,
            duration: 800,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true
          })
        ])
      ).start();

      Animated.timing(waveHeightAnim, {
        toValue: Math.max(8, 26 * audioLevel),
        duration: 120,
        useNativeDriver: false
      }).start();
    } else {
      pulseAnim.setValue(1);
      waveHeightAnim.setValue(6);
    }
  }, [isListening, audioLevel, pulseAnim, waveHeightAnim]);

  const spin1 = rotateAnim1.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg']
  });

  const spin2 = rotateAnim2.interpolate({
    inputRange: [0, 1],
    outputRange: ['360deg', '0deg']
  });

  return (
    <View style={styles.container}>
      {/* Outer Ambient Diffused Glow */}
      <View style={styles.ambientGlow} />

      <TouchableOpacity
        activeOpacity={0.88}
        onPress={onPress}
        style={styles.touchableArea}
      >
        <Animated.View
          style={[
            styles.orbBody,
            { transform: [{ scale: pulseAnim }] }
          ]}
        >
          {/* Outer Orbital Ring 1 */}
          <Animated.View
            style={[
              styles.orbitalRingOuter,
              { transform: [{ rotate: spin1 }] }
            ]}
          >
            <View style={styles.orbitDotTop} />
            <View style={styles.orbitDotBottom} />
          </Animated.View>

          {/* Inner Orbital Ring 2 */}
          <Animated.View
            style={[
              styles.orbitalRingInner,
              { transform: [{ rotate: spin2 }] }
            ]}
          />

          {/* Deep Plasma Sphere with Luminous Rim */}
          <View style={styles.plasmaCore}>
            {/* Top Specular Sheen */}
            <View style={styles.specularHighlight} />

            {/* J A R V I S Typography */}
            <Text style={styles.jarvisText}>J A R V I S</Text>

            {/* Dynamic Sound Waveform Bars */}
            <View style={styles.waveformRow}>
              {[0.4, 0.7, 1.0, 0.75, 0.5].map((multiplier, i) => (
                <View
                  key={i}
                  style={[
                    styles.waveformBar,
                    {
                      height: isListening ? Math.max(4, 22 * multiplier * (audioLevel + 0.3)) : 5
                    }
                  ]}
                />
              ))}
            </View>
          </View>
        </Animated.View>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: 14,
    position: 'relative'
  },
  touchableArea: {
    alignItems: 'center',
    justifyContent: 'center'
  },
  ambientGlow: {
    position: 'absolute',
    width: 260,
    height: 260,
    borderRadius: 130,
    backgroundColor: 'rgba(0, 229, 255, 0.12)',
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 50,
    elevation: 12
  },
  orbBody: {
    width: 220,
    height: 220,
    alignItems: 'center',
    justifyContent: 'center'
  },
  orbitalRingOuter: {
    position: 'absolute',
    width: 216,
    height: 216,
    borderRadius: 108,
    borderWidth: 1.5,
    borderColor: 'rgba(0, 229, 255, 0.35)',
    borderStyle: 'dashed'
  },
  orbitalRingInner: {
    position: 'absolute',
    width: 196,
    height: 196,
    borderRadius: 98,
    borderWidth: 1,
    borderColor: 'rgba(59, 130, 246, 0.35)'
  },
  orbitDotTop: {
    position: 'absolute',
    top: -3,
    left: '50%',
    marginLeft: -4,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#00e5ff',
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 6
  },
  orbitDotBottom: {
    position: 'absolute',
    bottom: -3,
    left: '50%',
    marginLeft: -3,
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#3b82f6',
    shadowColor: '#3b82f6',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 6
  },
  plasmaCore: {
    width: 168,
    height: 168,
    borderRadius: 84,
    backgroundColor: '#040b19',
    borderWidth: 2,
    borderColor: 'rgba(0, 229, 255, 0.65)',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.7,
    shadowRadius: 28,
    elevation: 10,
    overflow: 'hidden'
  },
  specularHighlight: {
    position: 'absolute',
    top: 6,
    width: 110,
    height: 38,
    borderRadius: 20,
    backgroundColor: 'rgba(255, 255, 255, 0.12)'
  },
  jarvisText: {
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 8,
    color: '#ffffff',
    textShadowColor: 'rgba(0, 229, 255, 0.9)',
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 12,
    marginLeft: 6
  },
  waveformRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 10,
    gap: 3.5
  },
  waveformBar: {
    width: 3.5,
    backgroundColor: '#00e5ff',
    borderRadius: 2,
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.9,
    shadowRadius: 4
  }
});
