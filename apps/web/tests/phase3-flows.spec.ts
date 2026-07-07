import { expect, test } from '@playwright/test';

test.describe('FieldSight Edge Phase 3 control center', () => {
  test('loads live mission control and core operational navigation', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('SAFE DEMO ENVIRONMENT')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Mission control' })).toBeVisible();
    await page.getByRole('link', { name: /Map workspace/i }).click();
    await expect(page.getByRole('heading', { name: /Project & site map/i })).toBeVisible();
  });

  test('shows media intake and explicit synthetic notice', async ({ page }) => {
    await page.goto('/media');
    await expect(page.getByRole('heading', { name: /Media intake center/i })).toBeVisible();
    await expect(page.getByText(/SIMULATION NOTICE/i)).toBeVisible();
  });

  test('loads tenant-scoped search UI', async ({ page }) => {
    await page.goto('/search');
    await page.getByLabel('Search field operations').fill('alpha');
    await expect(page.getByText(/Asset|Mission|Report/).first()).toBeVisible();
  });
});
