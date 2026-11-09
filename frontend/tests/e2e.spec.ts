import { test, expect } from '@playwright/test';

test.describe('SeeLess E2E Tests', () => {
  test('Landing page loads and has correct elements', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    // Check hero section
    await expect(page.locator('h1')).toContainText('Visual Descriptions');
    
    // Check CTA button
    await expect(page.locator('a[href="/dashboard"]')).toBeVisible();
    await expect(page.locator('text=Use Tool')).toBeVisible();
    
    // Check gradient background exists
    await expect(page.locator('svg')).toBeVisible();
  });

  test('Dashboard loads with empty state', async ({ page }) => {
    await page.goto('http://localhost:3000/dashboard');
    
    // Should show search and filters
    await expect(page.locator('input[placeholder="Search videos..."]')).toBeVisible();
    await expect(page.locator('select')).toBeVisible();
    
    // Should show empty state when no videos
    await expect(page.locator('text=No videos found')).toBeVisible();
    await expect(page.locator('text=Upload your first video to get started.')).toBeVisible();
  });

  test('Navigation works between pages', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    // Click dashboard link
    await page.click('a[href="/dashboard"]');
    await expect(page).toHaveURL(/\/dashboard/);
    
    // Click back to home
    await page.click('a[href="/"]');
    await expect(page).toHaveURL('/');
  });

  test('SVG gradient renders correctly', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    const svg = page.locator('svg');
    await expect(svg).toBeVisible();
    
    const stops = svg.locator('stop');
    await expect(stops).toHaveCount(2);
  });
});
