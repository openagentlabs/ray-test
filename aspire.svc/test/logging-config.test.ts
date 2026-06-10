import { afterEach, describe, expect, it } from "vitest";

import { LoggingConfigFactory } from "@/lib/config/logging-config";

describe("LoggingConfigFactory", () => {
  afterEach(() => {
    delete process.env.LOG_ENABLED;
    delete process.env.LOG_LEVEL;
    delete process.env.OTEL_SERVICE_NAME;
  });

  it("defaults log level to debug and logging enabled", () => {
    const config = LoggingConfigFactory.fromEnvironment();
    expect(config.logLevel).toBe("debug");
    expect(config.enabled).toBe(true);
  });

  it("parses LOG_LEVEL", () => {
    process.env.LOG_LEVEL = "warn";
    const config = LoggingConfigFactory.fromEnvironment();
    expect(config.logLevel).toBe("warn");
  });

  it("respects LOG_ENABLED=false", () => {
    process.env.LOG_ENABLED = "false";
    const config = LoggingConfigFactory.fromEnvironment();
    expect(config.enabled).toBe(false);
  });
});
