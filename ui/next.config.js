/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  pageExtensions: ['js', 'jsx', 'ts', 'tsx'],
  webpack: (config) => {
    // Exclude test files from build
    config.resolve.alias = {
      ...config.resolve.alias,
    }
    return config
  },
  experimental: {
    // Ignore test files during build
    forceSwcTransforms: true,
  },
  // Exclude test files from pages
  async rewrites() {
    return []
  },
  async redirects() {
    return []
  },
}

module.exports = nextConfig