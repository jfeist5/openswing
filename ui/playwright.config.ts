import { defineConfig, devices } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { PROFILES_PATH_ENV, uniqueE2eProfilesPath } from './tests/e2e/isolateProfilesPath';

const PORT = 5173;
const HOST = '127.0.0.1';
const BASE_URL = `http://${HOST}:${PORT}`;
const CONFIG_DIR = fileURLToPath(new URL('.', import.meta.url));
const BACKEND_ARGS = `--mock --host ${HOST} --web-port 8080 --no-logging`;
const BACKEND_COMMAND = `uv run openflight-server ${BACKEND_ARGS}`;

// Pitch-speed specs need their own backend mode, so they get a second backend and UI.
const PITCH_PORT = 5174;
const PITCH_BACKEND_PORT = 8081;
const PITCH_BASE_URL = `http://${HOST}:${PITCH_PORT}`;
const PITCH_BACKEND_URL = `http://${HOST}:${PITCH_BACKEND_PORT}`;
const PITCH_BACKEND_COMMAND = `uv run openflight-server --mock-pitch-speed --host ${HOST} --web-port ${PITCH_BACKEND_PORT} --no-logging`;
const PITCH_SPECS = '**/pitch-*.spec.ts';

const E2E_PROFILES_PATH = uniqueE2eProfilesPath();
const PITCH_E2E_PROFILES_PATH = uniqueE2eProfilesPath();

function processEnv(): { [key: string]: string } {
  const env: { [key: string]: string } = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (value !== undefined) env[key] = value;
  }
  return env;
}

function backendEnv(profilesPath = E2E_PROFILES_PATH): { [key: string]: string } {
  return { ...processEnv(), [PROFILES_PATH_ENV]: profilesPath };
}

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['html', { outputFolder: 'playwright-report', open: 'never' }], ['github']] : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: [
    {
      command: BACKEND_COMMAND,
      url: `http://${HOST}:8080`,
      reuseExistingServer: false,
      cwd: fileURLToPath(new URL('..', import.meta.url)),
      env: backendEnv(),
    },
    {
      command: `npm run dev -- --host ${HOST} --port ${PORT} --mode test`,
      url: BASE_URL,
      reuseExistingServer: !process.env.CI,
      cwd: CONFIG_DIR,
    },
    {
      command: PITCH_BACKEND_COMMAND,
      url: PITCH_BACKEND_URL,
      reuseExistingServer: false,
      cwd: fileURLToPath(new URL('..', import.meta.url)),
      env: backendEnv(PITCH_E2E_PROFILES_PATH),
    },
    {
      command: `npm run dev -- --host ${HOST} --port ${PITCH_PORT} --mode test`,
      url: PITCH_BASE_URL,
      reuseExistingServer: false,
      cwd: CONFIG_DIR,
      env: { ...processEnv(), VITE_SOCKET_URL: PITCH_BACKEND_URL },
    },
  ],
  projects: [
    {
      name: 'chromium',
      testIgnore: PITCH_SPECS,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'pitch',
      testMatch: PITCH_SPECS,
      use: { ...devices['Desktop Chrome'], baseURL: PITCH_BASE_URL },
    },
  ],
});
