/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  experimental: {
    forceSwcTransforms: true,
  },
  eslint: {
    // TODO: Remove this after fixing ESLint errors (tracked in issue)
    // Allows production builds to complete even with ESLint errors
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;
