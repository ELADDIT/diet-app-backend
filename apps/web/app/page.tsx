"use client";

import { AppShell } from '@diet/ui';
import { themeTokens } from '@diet/theme';
import { View, Text } from 'react-native';

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'recipes', label: 'Recipes' },
  { key: 'community', label: 'Community' }
];

export default function Page() {
  return (
    <View style={{ flex: 1 }}>
      <AppShell navigationItems={NAV_ITEMS} activeKey="dashboard" title="Analytics">
        <View>
          <Text style={{ color: themeTokens.colors.text, fontSize: 24, fontWeight: '700' }}>Today&apos;s Intake</Text>
          <Text style={{ color: themeTokens.colors.muted, maxWidth: 540, marginTop: 16 }}>
            Track macros, hydration, and recovery trends with a consistent neon aesthetic across mobile and web.
          </Text>
        </View>
      </AppShell>
    </View>
  );
}
