/** @type {import('next').NextConfig} */
const API = process.env.NEXT_PUBLIC_API_BASE || "";

const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  // dev-only proxy so the browser talks to one origin
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [{ source: "/api/:path*", destination: `${API || "http://127.0.0.1:8000"}/api/:path*` }];
  },
};

export default nextConfig;
