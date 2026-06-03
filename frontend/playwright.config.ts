import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI
  },
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure"
  },
  projects: [
    {
      name: "iphone-se",
      use: {
        ...devices["iPhone SE"],
        browserName: "chromium",
        viewport: { width: 320, height: 568 }
      }
    },
    {
      name: "pixel-7",
      use: {
        ...devices["Pixel 7"],
        browserName: "chromium"
      }
    },
    {
      name: "tablet",
      use: {
        ...devices["iPad Mini"],
        browserName: "chromium"
      }
    }
  ]
});
