import {defineConfig, devices} from '@playwright/test';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export default defineConfig({
  testDir: '../tests/web/browser', testMatch: '*.spec.mjs', workers: 1,
  use: {baseURL: 'http://127.0.0.1:8976', trace: 'retain-on-failure'},
  projects: [{name: 'desktop', use: {...devices['Desktop Chrome']}}, {name: 'mobile', use: {...devices['Pixel 7']}}],
  webServer: {
    command: `"${path.join(root, '.venv', process.platform==='win32'?'Scripts/python.exe':'bin/python')}" tests/web/browser/server.py 8976`,
    cwd: root, url: 'http://127.0.0.1:8976/test-fixture', reuseExistingServer: false, timeout: 30000,
  },
});
