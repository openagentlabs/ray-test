import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  {
    settings: {
      next: {
        rootDir: ".",
      },
    },
  },
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    "**/.next/**",
    "**/out/**",
    "**/build/**",
    "**/node_modules/**",
    "package-lock.json",
  ]),
]);

export default eslintConfig;
