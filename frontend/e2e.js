const { chromium } = require('playwright');
const path = require('path');

const artifactsDir = '/home/alucard/.gemini/antigravity/brain/37461850-b133-4085-ba9a-df449b7ae4bd/';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  await page.goto('http://localhost:3000');
  
  await page.waitForSelector('textarea');

  // Edge Case 1 - Empty Input
  console.log("Running Edge Case 1: Empty Input");
  await page.fill('textarea', '');
  await page.click('button:has-text("Submit")', { force: true });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(artifactsDir, 'empty_input.png') });

  // Edge Case 2 - Extreme Length
  console.log("Running Edge Case 2: Extreme Length");
  const longText = 'A'.repeat(10000);
  await page.fill('textarea', longText);
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(artifactsDir, 'extreme_length.png') });
  await page.fill('textarea', '');

  // Edge Case 3 - XSS
  console.log("Running Edge Case 3: XSS");
  await page.fill('textarea', '<h1>Overridden</h1><script>alert(1)</script>');
  await page.click('button:has-text("Submit")');
  await page.waitForTimeout(1000); 
  await page.screenshot({ path: path.join(artifactsDir, 'xss.png') });

  // Edge Case 4 - Rapid Fire
  console.log("Running Edge Case 4: Rapid Fire");
  await page.fill('textarea', 'Prompt 1');
  await page.click('button:has-text("Submit")');
  await page.fill('textarea', 'Prompt 2');
  await page.click('button:has-text("Submit")', { force: true });
  await page.fill('textarea', 'Prompt 3');
  await page.click('button:has-text("Submit")', { force: true });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(artifactsDir, 'rapid_fire.png') });
  
  // Happy Path
  console.log("Running Happy Path");
  const page2 = await context.newPage();
  await page2.goto('http://localhost:3000');
  await page2.waitForSelector('textarea');
  await page2.fill('textarea', 'Tell me a quote about the abyss, and compare "Nietzsche" and "Socrates"');
  await page2.click('button:has-text("Submit")');
  
  console.log("Waiting for backend response...");
  await page2.waitForFunction(() => {
    const btn = document.querySelector('button');
    return btn && !btn.disabled;
  }, { timeout: 60000 }).catch(e => console.log("Timeout waiting for response"));
  
  await page2.waitForTimeout(2000);
  await page2.screenshot({ path: path.join(artifactsDir, 'happy_path.png') });

  await browser.close();
  console.log("Done");
})();
