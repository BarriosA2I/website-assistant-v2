/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  
  // Enable standalone output for Docker
  output: 'standalone',
  
  // Image optimization
  images: {
    domains: ['barriosa2i.com', 'cdn.barriosa2i.com'],
    formats: ['image/avif', 'image/webp'],
  },
  
  // Rewrites for API proxy
  async rewrites() {
    return [
      {
        source: '/api/v2/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:8000'}/api/v2/:path*`,
      },
    ];
  },
  
  // Headers for security
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
