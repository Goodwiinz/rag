const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React strict mode
  reactStrictMode: true,

  // Turbopack configuration (Next.js 16 default)
  turbopack: {},

  // Standalone output for Docker deployments
  output: 'standalone',

  // Output file tracing root for monorepo (must be relative for Docker compatibility)
  outputFileTracingRoot: path.join(__dirname, '..'),

  // Ignore TypeScript build errors temporarily
  typescript: {
    ignoreBuildErrors: process.env.NODE_ENV !== 'production',
  },

  // Next.js build lint integration still passes legacy CLI options that do not
  // work with the flat ESLint config used by this app. Keep linting in the
  // dedicated npm script instead.
  eslint: {
    ignoreDuringBuilds: true,
  },

  // Experimental features for better performance
  experimental: {
    optimizeCss: true,
    optimizePackageImports: ['lucide-react', '@radix-ui/react-icons'],
  },

  // Granular import transforms for better tree-shaking
  modularizeImports: {
    'lucide-react': {
      transform: 'lucide-react/dist/esm/icons/{{kebabCase member}}',
      preventFullImport: true,
    },
    '@radix-ui/react-icons': {
      transform: '@radix-ui/react-icons/dist/{{kebabCase member}}',
      preventFullImport: true,
    },
  },

  // Build compiler options
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production',
  },

  // Remove the X-Powered-By header
  poweredByHeader: false,

  // Image optimization
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
      },
    ],
    formats: ['image/webp', 'image/avif'],
    minimumCacheTTL: 60 * 60 * 24 * 7, // 7 days
  },

  // Webpack configuration for file uploads
  webpack: (config, { isServer }) => {
    // Handle file uploads for documents
    config.module.rules.push({
      test: /\.(pdf|docx?|txt|jpe?g|png|mp3|mp4|mov|avi|wav)$/i,
      use: [
        {
          loader: 'file-loader',
          options: {
            publicPath: '/_next/static/files/',
            outputPath: 'static/files/',
            name: '[name].[hash].[ext]',
          },
        },
      ],
    });

    // Handle source maps in development
    if (!isServer) {
      config.resolve.alias = {
        ...config.resolve.alias,
        fs: false,
      };
    }

    return config;
  },

  // API configuration
  async rewrites() {
    // Use BACKEND_URL env var if set (for Docker), otherwise default to localhost
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    return [
      // API rewrites for backend integration
      {
        source: '/api/v1/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
      {
        source: '/api/v2/:path*',
        destination: `${backendUrl}/api/v2/:path*`,
      },
    ];
  },

  // Environment variables
  // Do NOT set localhost fallbacks here — they get baked into the production
  // JS bundle and cause CORS/mixed-content errors in K8s deployments.
  // The frontend uses Next.js rewrites (/api/v1/* → backend) when these are unset.
  env: {
    ...(process.env.NEXT_PUBLIC_API_URL
      ? { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL }
      : {}),
    ...(process.env.NEXT_PUBLIC_WS_URL
      ? { NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL }
      : {}),
  },

  // Combined CORS and Security headers
  async headers() {
    return [
      {
        source: '/api/:path*',
        headers: [
          {
            key: 'Access-Control-Allow-Origin',
            value:
              process.env.NEXT_PUBLIC_FRONTEND_URL || 'http://localhost:3000',
          },
          {
            key: 'Access-Control-Allow-Methods',
            value: 'GET, POST, PUT, DELETE, OPTIONS',
          },
          {
            key: 'Access-Control-Allow-Headers',
            value: 'Content-Type, Authorization',
          },
        ],
      },
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'origin-when-cross-origin' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'X-DNS-Prefetch-Control', value: 'on' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
          { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
        ],
      },
    ];
  },

  // Redirects for common routes
  async redirects() {
    return [
      {
        source: '/home',
        destination: '/',
        permanent: true,
      },
    ];
  },
};

module.exports = nextConfig;
