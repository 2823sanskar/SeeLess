const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function run() {
  const videoPath = 'C:\\Users\\Admin\\Downloads\\vidssave.com THE OTHER GUYS - FUNNY SCENE - OFFICE ARGUMENT 720P (1).mp4';
  if (!fs.existsSync(videoPath)) {
    console.error('Video file not found at:', videoPath);
    process.exit(1);
  }

  console.log('Launching Chromium...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('console', msg => console.log('[BROWSER CONSOLE]', msg.type(), msg.text()));
  page.on('pageerror', err => console.error('[BROWSER ERROR]', err.message));
  page.on('requestfailed', req => console.error('[REQ FAILED]', req.url(), req.failure()?.errorText));
  page.on('response', resp => {
    if (resp.status() >= 400) {
      console.error('[HTTP ERROR]', resp.status(), resp.url());
    }
  });

  console.log('Navigating to http://localhost:3000...');
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'screenshot_home.png' });
  console.log('Home page loaded. Title:', await page.title());

  console.log('Uploading video file to input...');
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(videoPath);
  await page.waitForTimeout(1000);

  await page.screenshot({ path: 'screenshot_file_selected.png' });
  console.log('File selected. Button text checking...');

  const button = page.locator('button:has-text("Start AI Accessibility Processing"), button:has-text("Processing"), button:has-text("Upload")').first();
  console.log('Clicking upload button...');
  await button.click();

  console.log('Waiting for URL change or upload response...');
  // Wait up to 60s for redirect to /processing/...
  try {
    await page.waitForURL(url => url.pathname.includes('/processing/'), { timeout: 60000 });
    console.log('Successfully redirected to:', page.url());
    await page.screenshot({ path: 'screenshot_processing_page.png' });

    // Poll status on the processing page for up to 300 seconds
    const videoId = page.url().split('/processing/')[1].split('/')[0];
    console.log('Processing videoId:', videoId);

    for (let i = 0; i < 40; i++) {
      await page.waitForTimeout(5000);
      const text = await page.textContent('body');
      console.log(`[Status check #${i+1}] Current URL:`, page.url());
      if (page.url().includes('/result/')) {
        console.log('Processing completed! Reached result page:', page.url());
        await page.screenshot({ path: 'screenshot_result_page.png' });
        break;
      }
      if (text.includes('Failed') || text.includes('error')) {
        console.log('[Page alert text]:', text.slice(0, 300));
      }
    }
  } catch (err) {
    console.error('Wait for redirect / processing error:', err.message);
    const bodyText = await page.textContent('body');
    console.error('Current page text:', bodyText.slice(0, 400));
    await page.screenshot({ path: 'screenshot_error.png' });
  }

  await browser.close();
}

run().catch(err => {
  console.error('Fatal test error:', err);
  process.exit(1);
});

