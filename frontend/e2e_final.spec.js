const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const OUT_DIR = '/home/alucard/.gemini/antigravity/brain/37461850-b133-4085-ba9a-df449b7ae4bd';

async function runTests() {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  // Helper to run a test
  async function runPromptTest(name, prompt, waitSelector = null, timeout = 30000) {
    console.log(`Running test: ${name}`);
    await page.goto('http://localhost:3000');
    // Wait for the textarea to be available
    await page.waitForSelector('textarea');
    await page.fill('textarea', prompt);
    // Submit (Enter key or find the submit button)
    await page.keyboard.press('Enter');

    if (waitSelector) {
        try {
            await page.waitForSelector(waitSelector, { timeout });
            // wait a little bit extra for animations/streaming to settle
            await page.waitForTimeout(2000);
        } catch(e) {
            console.log(`Timeout waiting for ${waitSelector}`);
        }
    } else {
        // Just wait a bit for streaming
        await page.waitForTimeout(10000);
    }
    
    const screenshotPath = path.join(OUT_DIR, `${name}.png`);
    await page.screenshot({ path: screenshotPath });
    console.log(`Saved screenshot: ${screenshotPath}`);
  }

  // 1. RAG & Persona Test
  await runPromptTest(
    'rag_persona',
    'I feel overwhelmed by the absurdity of my daily office work. What would Camus or Nietzsche say to me right now?',
    '.prose p', // wait for some paragraph to appear
    15000
  );

  // 2. UI Effects Test
  await runPromptTest(
    'ui_effects',
    'Give me a direct quote from Socrates and tell me about Plato.',
    '.philosopher-badge', // wait for badge
    15000
  );

  // 3. XSS Injection Test
  await runPromptTest(
    'xss_injection',
    "<script>alert('hack')</script><h1>Overridden</h1>",
    '.prose p',
    10000
  );

  // 4. Extreme Overflow Test
  const overflowStr = 'A'.repeat(5000);
  await runPromptTest(
    'extreme_overflow',
    overflowStr,
    'textarea',
    10000
  );

  await browser.close();
  console.log("All tests finished.");
}

runTests().catch(console.error);
