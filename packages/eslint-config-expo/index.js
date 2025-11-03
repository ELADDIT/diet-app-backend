module.exports = {
  extends: ['plugin:react/recommended', 'plugin:react-hooks/recommended', 'plugin:react-native/all'],
  plugins: ['react', 'react-hooks', 'react-native'],
  settings: {
    react: {
      version: 'detect',
    },
  },
  rules: {
    'react/react-in-jsx-scope': 'off',
  },
};
