import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet } from 'react-native';

export type GradientProps = {
  colors: string[];
};

export const GradientComponent = ({ colors }: GradientProps) => {
  return <LinearGradient colors={colors} style={StyleSheet.absoluteFill} start={[0, 0]} end={[1, 1]} pointerEvents="none" />;
};
