import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  test: {
    environment: "node",
    include: [
      path.join(__dirname, "testing/unit/**/*.test.ts"),
      path.join(__dirname, "testing/integration/**/*.test.ts"),
    ],
  },
});
