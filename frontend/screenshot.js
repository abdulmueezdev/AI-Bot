const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 375, height: 812 },
    isMobile: true,
    hasTouch: true
  });
  const page = await context.newPage();
  
  try {
    await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    
    // Disable blinking cursor for screenshots
    await page.addStyleTag({ content: '.blinking-cursor { animation: none !important; opacity: 1 !important; }' });
    
    await page.fill('textarea', 'Hi');
    await page.click('button:has-text("Submit")');
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'mobile_screenshot_3.png' });
    
    // Wait for the response (which will fail and say "THE SYSTEM IS UNRESPONSIVE" because backend isn't running)
    await page.waitForTimeout(2000);
    
    await page.fill('textarea', 'Another long message to fill up the space on the mobile screen.');
    await page.click('button:has-text("Submit")');
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'mobile_screenshot_4.png' });
    
  } catch (err) {
    console.error(err);
  } finally {
    await browser.close();
  }
})();
