const { withExpo } = require('@expo/next-adapter');

const nextConfig = withExpo({
  reactStrictMode: true,
  transpilePackages: ['@diet/ui', '@diet/theme']
});

module.exports = nextConfig;
