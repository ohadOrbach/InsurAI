/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable API rewrites to proxy backend calls
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;

