import { Platform } from 'react-native';
import { GradientComponent as NativeGradient, GradientProps } from './createGradientComponent.native';
import { GradientComponent as WebGradient } from './createGradientComponent.web';

export type { GradientProps };

export const AnimatedGradientBackground = (props: GradientProps) => {
  if (Platform.OS === 'web') {
    return <WebGradient {...props} />;
  }

  return <NativeGradient {...props} />;
};
