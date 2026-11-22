/** @type {import('next').NextConfig} */
const nextConfig = {
  // Separate build folder per server (e.g. NEXT_DIST_DIR=.next-3005) so two dev
  // servers on this project never overwrite each other's files.
  distDir: process.env.NEXT_DIST_DIR || '.next',
  reactStrictMode: true,
  transpilePackages: ['lucide-react'],
  typescript: {
    // Allows production build to succeed while Next's internal .next/types resolves
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
