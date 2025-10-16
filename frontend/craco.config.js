const path = require('path');

module.exports = {
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {
      // Ensure the source map is configured correctly for debugging
      webpackConfig.devtool = webpackConfig.mode === 'development' ? 'eval-source-map' : false;
      return webpackConfig;
    },
  },
  jest: {
    configure: {
      moduleNameMapping: {
        '^@/(.*)$': '<rootDir>/src/$1',
      },
    },
  },
};