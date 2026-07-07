import { test, expect } from '@playwright/test';
test('landing positions industrial inspection workflow', async ({ page }) => { await page.goto('/landing'); await expect(page.getByText('AI inspection from field capture to')).toBeVisible(); await expect(page.getByText('Enter Control Center')).toBeVisible(); });
