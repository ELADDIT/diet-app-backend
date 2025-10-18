module.exports = {
  preset: 'jest-expo',
  transformIgnorePatterns: [
    'node_modules/(?!(expo(nent)?|@expo|react-native|@react-native|@react-navigation|nativewind)/)'
  ]
};
