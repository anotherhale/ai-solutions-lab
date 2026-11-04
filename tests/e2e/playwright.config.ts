import { defineConfig, devices } from "@playwright/test";

const reviewApp = "../../apps/wasatch-review";
const apiPort = process.env.WASATCH_E2E_API_PORT ?? "8010";
const apiOrigin = `http://127.0.0.1:${apiPort}`;

export default defineConfig({
  testDir: "./specs",
  fullyParallel: false,
  workers: 1,
  // Retries reuse one seeded database; approve/accept specs mutate fixture rows.
  retries: 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "bash ../../scripts/run_wasatch_api_host.sh",
      url: `${apiOrigin}/health`,
      timeout: 180_000,
      reuseExistingServer: !process.env.CI,
      env: {
        API_PORT: apiPort,
        WASATCH_DATABASE_URL:
          process.env.WASATCH_DATABASE_URL ??
          "postgresql+psycopg://wasatch:replace-me@localhost:5432/wasatch_test",
        WASATCH_REQUIRE_DATABASE: "1",
        APP_ENV: "test",
        AI_PROVIDER: "fake",
      },
    },
    {
      command: "npm run build && npm run preview -- --host 127.0.0.1 --port 5173",
      cwd: reviewApp,
      url: "http://127.0.0.1:5173",
      timeout: 180_000,
      reuseExistingServer: !process.env.CI,
      env: {
        WASATCH_API_PROXY: apiOrigin,
      },
    },
  ],
});
