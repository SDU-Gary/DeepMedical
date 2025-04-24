/**
 * Run `build` or `dev` with `SKIP_ENV_VALIDATION` to skip env validation. This is especially useful
 * for Docker builds.
 */
import "./src/env.js";

/** @type {import("next").NextConfig} */
const config = {
  // 新增代理配置
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
      // 处理预检请求
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
        has: [{ type: "header", key: "Access-Control-Request-Method" }]
      }
    ]
  },
  webpack: (config) => {
    config.module.rules.push({
      test: /\.txt$/,
      use: "raw-loader",
    });
    return config;
  },
  experimental: {
    turbo: {
      rules: {
        "*.txt": {
          loaders: ["raw-loader"],
          as: "*.js",
        },
      },
    },
  },
  // ... rest of the configuration.
  output: "standalone",
};


export default config;
