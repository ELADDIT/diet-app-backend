declare module 'react-native' {
  export const Platform: { OS: string };
  export const Pressable: (props: any) => any;
  export const StyleSheet: {
    create<T extends Record<string, any>>(styles: T): T;
    absoluteFill: any;
  };
  export const Text: (props: any) => any;
  export const View: (props: any) => any;
  export function useWindowDimensions(): { width: number; height: number };
}
