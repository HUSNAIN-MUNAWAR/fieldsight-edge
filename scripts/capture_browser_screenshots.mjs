/**
 * Runs only in a Playwright-capable environment with API and web server started.
 * Captures actual rendered API-driven routes; it never creates mock PNGs.
 */
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputDir = path.join(rootDir, 'docs', 'screenshots');
const require = createRequire(path.join(rootDir, 'apps', 'web', 'package.json'));
const { chromium } = require('@playwright/test');

const baseURL = process.env.FIELDSIGHT_WEB_URL || 'http://127.0.0.1:3000';
const apiURL = process.env.FIELDSIGHT_API_URL || 'http://127.0.0.1:8000';
const routes = [
  ['01-landing-page', '/landing'], ['02-mission-control', '/'], ['03-command-map', '/map'],
  ['04-mission-planning', '/missions'], ['05-media-intake', '/media'], ['06-review-workspace', '/review'],
  ['07-asset-risk', '/risk'], ['08-work-order', '/defects'], ['09-edge-fleet', '/devices'],
  ['10-model-governance', '/models'], ['11-reporting', '/reports'], ['12-security', '/security'],
  ['13-operations', '/operations'], ['14-global-search', '/search'],
];
const readySelectors = {
  '/': '.mission-hero',
  '/map': '.big-map',
  '/review': '.annotation-stage',
  '/defects': '.defect-table',
  '/devices': '.device-grid',
  '/models': '.model-grid',
  '/reports': '.report-layout',
  '/operations': '.ops-grid',
};

await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
for (const [name, route] of routes) {
  await page.goto(`${baseURL}${route}`, { waitUntil: 'networkidle', timeout: 45_000 });
  const selector = readySelectors[route];
  if (selector) {
    await page.waitForSelector(selector, { state: 'visible', timeout: 45_000 });
  }
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage: true });
}
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${baseURL}/field`, { waitUntil: 'networkidle', timeout: 45_000 });
await page.waitForTimeout(700);
await page.screenshot({ path: path.join(outputDir, '15-mobile-field-operator.png'), fullPage: true });
await page.setViewportSize({ width: 1600, height: 1000 });
await page.goto(`${apiURL}/docs`, { waitUntil: 'networkidle', timeout: 45_000 });
await page.waitForSelector('.swagger-ui', { state: 'visible', timeout: 45_000 });
await page.waitForTimeout(700);
await page.screenshot({ path: path.join(outputDir, '16-api-docs.png'), fullPage: true });
await browser.close();
