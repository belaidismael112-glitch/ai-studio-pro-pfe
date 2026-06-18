/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  images: {
    // solution 1 (simple): allow these domains
    domains: ["replicate.delivery", "localhost", "127.0.0.1"],

    // solution 2 (stronger, optional): allow exact local patterns (keeps domains above ok)
    remotePatterns: [
      {
        protocol: "http",
        hostname: "127.0.0.1",
        port: "8188",
        pathname: "/**",
      },
      {
        protocol: "http",
        hostname: "localhost",
        port: "8188",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "replicate.delivery",
        pathname: "/**",
      },
    ],
  },

  env: {
    API_BASE_URL: process.env.API_BASE_URL || "http://localhost:8000/api/v1",
  },
};

module.exports = nextConfig;