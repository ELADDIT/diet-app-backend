import { View, Text } from 'react-native';
import { AppShell } from '@diet/ui';
import { themeTokens } from '@diet/theme';

const NAV_ITEMS = [
  { key: 'home', label: 'Home' },
  { key: 'meals', label: 'Meals' },
  { key: 'progress', label: 'Progress' }
];

export default function Index() {
  return (
    <AppShell navigationItems={NAV_ITEMS} activeKey="home" title="Dashboard">
      <View>
        <Text style={{ color: themeTokens.colors.text, fontSize: 18, fontWeight: '600' }}>
          Welcome to the neon-fueled nutrition tracker.
        </Text>
        <Text style={{ color: themeTokens.colors.muted, fontSize: 14, marginTop: 12 }}>
          Start logging meals to see tailored macro insights ripple through your day.
        </Text>
      </View>
    </AppShell>
  );
}
