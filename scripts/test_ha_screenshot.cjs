// A screenshot of a page of the test Home Assistant, logged in as its owner.
//
//   NODE_PATH=$(npm root -g) node scripts/test_ha_screenshot.cjs \
//       /config/devices/dashboard out.png [refresh_token_file]
//
// The frontend reads its session from localStorage, so the owner's tokens
// (written by test_ha.py) are put there before the page loads.

const { readFileSync } = require("node:fs");
const { chromium } = require("playwright");

const [path = "/", out = "screenshot.png", tokensFile = ".test-ha/tokens.json"] =
  process.argv.slice(2);
const base = "http://127.0.0.1:8123";
const tokens = JSON.parse(readFileSync(tokensFile, "utf8"));

(async () => {
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || undefined,
});
const page = await browser.newPage({
  viewport: { width: 430, height: 1100 },
  locale: "fr-FR",
  timezoneId: "Europe/Paris",
});

await page.addInitScript(
  ({ tokens, base }) => {
    localStorage.setItem(
      "hassTokens",
      JSON.stringify({
        ...tokens,
        hassUrl: base,
        clientId: base + "/",
        expires: Date.now() + tokens.expires_in * 1000,
      })
    );
  },
  { tokens, base }
);

await page.goto(base + path, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
await page.screenshot({ path: out, fullPage: true });
await browser.close();
})();
