import { ReactNode, useMemo } from 'react';
import { Platform, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { themeTokens } from '@diet/theme';
import { AnimatedGradientBackground } from '../motion/GradientBackground';

type NavigationItem = {
  key: string;
  label: string;
  icon?: ReactNode;
  onPress?: () => void;
};

type AppShellProps = {
  navigationItems: NavigationItem[];
  activeKey?: string;
  title?: string;
  children: ReactNode;
  gradientColors?: string[];
};

const MOBILE_MAX_WIDTH = 900;

export const AppShell = ({
  navigationItems,
  activeKey,
  title,
  children,
  gradientColors = [themeTokens.colors.neon.blue, themeTokens.colors.neon.purple]
}: AppShellProps) => {
  const { width } = useWindowDimensions();
  const isMobile = width <= MOBILE_MAX_WIDTH;

  const gradientStops = useMemo(() => gradientColors, [gradientColors]);

  return (
    <View style={styles.root}>
      <AnimatedGradientBackground colors={gradientStops} />
      <View style={styles.contentWrapper}>
        {isMobile ? (
          <MobileLayout navigationItems={navigationItems} activeKey={activeKey} title={title}>
            {children}
          </MobileLayout>
        ) : (
          <WebLayout navigationItems={navigationItems} activeKey={activeKey} title={title}>
            {children}
          </WebLayout>
        )}
      </View>
    </View>
  );
};

type LayoutProps = {
  navigationItems: NavigationItem[];
  activeKey?: string;
  title?: string;
  children: ReactNode;
};

const MobileLayout = ({ navigationItems, activeKey, title, children }: LayoutProps) => (
  <View style={styles.mobileContainer}>
    <View style={styles.page}>{title ? <Text style={styles.pageTitle}>{title}</Text> : null}{children}</View>
    <View style={styles.mobileNav}>
      {navigationItems.map((item) => (
        <Pressable
          key={item.key}
          onPress={item.onPress}
          style={[styles.mobileNavItem, activeKey === item.key && styles.mobileNavItemActive]}
        >
          {item.icon}
          <Text style={[styles.mobileNavLabel, activeKey === item.key && styles.mobileNavLabelActive]}>
            {item.label}
          </Text>
        </Pressable>
      ))}
    </View>
  </View>
);

const WebLayout = ({ navigationItems, activeKey, title, children }: LayoutProps) => (
  <View style={styles.webContainer}>
    <View style={styles.sidebar}>
      <Text style={styles.brand}>NeonDiet</Text>
      {navigationItems.map((item) => (
        <Pressable key={item.key} onPress={item.onPress} style={styles.sidebarItem}>
          <View
            style={[
              styles.sidebarPill,
              activeKey === item.key && {
                backgroundColor: 'rgba(0, 246, 255, 0.18)',
                shadowColor: themeTokens.colors.neon.blue,
                shadowOffset: { width: 0, height: 12 },
                shadowOpacity: 0.7,
                shadowRadius: 24,
                ...(Platform.OS === 'web'
                  ? { boxShadow: themeTokens.depth.intense }
                  : {})
              }
            ]}
          >
            <Text style={[styles.sidebarLabel, activeKey === item.key && styles.sidebarLabelActive]}>
              {item.label}
            </Text>
          </View>
        </Pressable>
      ))}
    </View>
    <View style={styles.webMain}>
      <View style={styles.topBar}>
        {title ? <Text style={styles.topBarTitle}>{title}</Text> : <View />}
        <View style={styles.topBarActions}>{/* placeholder for actions */}</View>
      </View>
      <View style={styles.page}>{children}</View>
    </View>
  </View>
);

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: themeTokens.colors.background,
    position: 'relative',
    overflow: 'hidden'
  },
  contentWrapper: {
    flex: 1,
    paddingTop: Platform.OS === 'web' ? 24 : 0,
    zIndex: 1
  },
  page: {
    flex: 1,
    paddingHorizontal: 24,
    paddingVertical: 32,
    paddingBottom: Platform.OS === 'web' ? 32 : 120
  },
  pageTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: themeTokens.colors.text,
    marginBottom: 24
  },
  mobileContainer: {
    flex: 1
  },
  mobileNav: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingHorizontal: 24,
    paddingVertical: 16,
    backgroundColor: 'rgba(3, 7, 18, 0.85)',
    borderTopWidth: Platform.OS === 'web' ? 1 : 0,
    borderColor: 'rgba(148, 163, 184, 0.15)',
    ...(Platform.OS === 'web' ? { backdropFilter: 'blur(12px)' } : {})
  },
  mobileNavItem: {
    alignItems: 'center'
  },
  mobileNavItemActive: {
    transform: [{ translateY: -4 }]
  },
  mobileNavLabel: {
    color: themeTokens.colors.muted,
    fontSize: 12,
    marginTop: 4
  },
  mobileNavLabelActive: {
    color: themeTokens.colors.neon.blue
  },
  webContainer: {
    flex: 1,
    flexDirection: 'row',
    paddingHorizontal: 32
  },
  sidebar: {
    width: 220,
    paddingVertical: 48,
    marginRight: 24
  },
  brand: {
    fontSize: 28,
    fontWeight: '800',
    color: themeTokens.colors.neon.pink,
    marginBottom: 32
  },
  sidebarItem: {
    borderRadius: 20,
    marginBottom: 16
  },
  sidebarPill: {
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: 20,
    backgroundColor: 'rgba(11, 18, 32, 0.65)'
  },
  sidebarLabel: {
    color: themeTokens.colors.muted,
    fontSize: 16,
    fontWeight: '500'
  },
  sidebarLabelActive: {
    color: themeTokens.colors.text
  },
  webMain: {
    flex: 1,
    borderRadius: 24,
    backgroundColor: 'rgba(11, 18, 32, 0.92)',
    padding: 32,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 40 },
    shadowOpacity: 0.35,
    shadowRadius: 60
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 24
  },
  topBarTitle: {
    fontSize: 30,
    fontWeight: '700',
    color: themeTokens.colors.text
  },
  topBarActions: {
    flexDirection: 'row'
  }
});

export type { AppShellProps, NavigationItem };
