/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable React strict mode
  reactStrictMode: true,

  // Turbopack configuration (Next.js 16 default)
  turbopack: {},

  // Standalone output for Docker deployments
  output: 'standalone',

  // Output file tracing root to resolve workspace warning
  outputFileTracingRoot: '/home/clawdbot/clawd',

  // Ignore TypeScript build errors temporarily
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },

  // Experimental features for better performance
  experimental: {
    // Optimize CSS
    optimizeCss: true,
    // Optimize package imports
    optimizePackageImports: ['lucide-react', '@radix-ui/react-icons'],
  },

  // Image optimization
  images: {
    domains: ['localhost'],
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
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  },

  // Combined CORS and Security headers
  async headers() {
    return [
      {
        source: '/api/:path*',
        headers: [
          { key: 'Access-Control-Allow-Origin', value: '*' },
          { key: 'Access-Control-Allow-Methods', value: 'GET, POST, PUT, DELETE, OPTIONS' },
          { key: 'Access-Control-Allow-Headers', value: 'Content-Type, Authorization' },
        ],
      },
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'origin-when-cross-origin',
          },
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