const assert = require('node:assert/strict');
const { chromium } = require(process.env.MAXWELL_TEST_PLAYWRIGHT);

(async () => {
  const origin = process.argv[2];
  const browser = await chromium.launch({
    executablePath: process.env.MAXWELL_TEST_CHROMIUM,
    headless: true,
    args: ['--no-sandbox', '--disable-background-networking'],
  });
  try {
    const context = await browser.newContext();
    const unexpected = [];
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin !== origin) {
        unexpected.push(route.request().url());
        return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/admin');
    assert.equal(page.url(), origin + '/admin/');
    await page.locator('#user').fill('synthetic-admin');
    await page.locator('#pass').fill('synthetic-dashboard-password');
    await page.locator('#loginForm button[type="submit"]').click();
    await page.locator('#app.authed').waitFor();
    await page.locator('[data-tab="controls"]').click();
    const personality = page.locator('[data-ctl="base_personality"]');
    await personality.fill('Synthetic browser personality');
    const saved = page.waitForResponse(response =>
      response.url() === origin + '/api/control' && response.request().method() === 'PUT');
    await personality.locator('xpath=ancestor::div[contains(@class,"card")]')
      .locator('[data-save-sec]').click();
    assert.equal((await saved).status(), 200);
    await page.reload();
    await page.locator('#app.authed').waitFor();
    await page.locator('[data-tab="controls"]').click();
    assert.equal(await personality.inputValue(), 'Synthetic browser personality');
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(await page.evaluate(() =>
        document.documentElement.scrollWidth <= window.innerWidth), true);
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(unexpected, []);
    await context.close();
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
