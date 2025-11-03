module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    project: './tsconfig.json',
  },
  env: {
    es2021: true,
    node: true,
    jest: true,
  },
  plugins: ['@typescript-eslint', 'react', 'react-hooks', 'react-native'],
  extends: ['expo', 'plugin:react-hooks/recommended', 'plugin:react-native/all', 'prettier'],
  settings: {
    react: {
      version: 'detect',
    },
  },
  ignorePatterns: ['node_modules/', '.expo/', 'dist/', 'build/', 'tailwind.config.ts'],
  rules: {
    'react-native/no-inline-styles': 'off',
  },
};
