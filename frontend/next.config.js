/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Vercel handles output automatically - no need for standalone
  // Enable standalone output only for Docker deployments
  ...(process.env.DOCKER_BUILD === 'true' ? { output: 'standalone' } : {}),

  // Image optimization
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'barriosa2i.com' },
      { protocol: 'https', hostname: 'cdn.barriosa2i.com' },
      { protocol: 'https', hostname: 'storage.googleapis.com' },
      { protocol: 'https', hostname: 's3.amazonaws.com' },
      { protocol: 'https', hostname: '*.run.app' },
    ],
    formats: ['image/avif', 'image/webp'],
  },

  // Rewrites for API proxy (works in both dev and Vercel)
  async rewrites() {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/v2/:path*',
        destination: `${backendUrl}/api/v2/:path*`,
      },
      {
        source: '/api/v3/:path*',
        destination: `${backendUrl}/api/v3/:path*`,
      },
      {
        source: '/webhook/:path*',
        destination: `${backendUrl}/webhook/:path*`,
      },
      {
        source: '/health',
        destination: `${backendUrl}/health`,
      },
    ];
  },

  // Headers for security
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
        ],
      },
    ];
  },

  // Environment variables exposed to browser
  env: {
    NEXT_PUBLIC_APP_NAME: 'Barrios A2I Website Assistant',
    NEXT_PUBLIC_APP_VERSION: '3.0.0',
  },

  // Compiler options for production
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production' ? { exclude: ['error', 'warn'] } : false,
  },

  // Experimental features
  experimental: {
    optimizeCss: true,
  },
};

module.exports = nextConfig;
