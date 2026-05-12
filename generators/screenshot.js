/**
 * Renderiza HTML como PNG via Puppeteer.
 * Se outputPng contiver "{index}", captura todos os .slide e substitui o index.
 * Uso: node generators/screenshot.js <html_file> <output_png> [width] [height]
 */

const puppeteer = require("puppeteer");
const path = require("path");
const fs = require("fs");

async function main() {
  const [, , htmlFile, outputPng, width = "1080", height = "1350"] = process.argv;

  if (!htmlFile || !outputPng) {
    console.error("Uso: node screenshot.js <html_file> <output_png> [width] [height]");
    process.exit(1);
  }

  const absoluteHtml = path.resolve(htmlFile);
  if (!fs.existsSync(absoluteHtml)) {
    console.error(`Arquivo não encontrado: ${absoluteHtml}`);
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    headless: "new",
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--allow-file-access-from-files",
      "--disable-web-security",
      "--disable-features=IsolateOrigins,site-per-process",
    ],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: parseInt(width), height: parseInt(height) });
  await page.goto(`file://${absoluteHtml}`, { waitUntil: "networkidle0" });

  await new Promise((r) => setTimeout(r, 1500));

  if (outputPng.includes("{index}")) {
    const slides = await page.$$('.slide');
    if (slides.length === 0) {
      console.error("Nenhum .slide encontrado para capturar.");
      await browser.close();
      process.exit(1);
    }
    for (let i = 0; i < slides.length; i++) {
      const p = outputPng.replace("{index}", String(i + 1).padStart(2, "0"));
      await slides[i].screenshot({ path: p });
      console.log(`PNG salvo: ${p}`);
    }
  } else {
    // Modo antigo de um slide só
    await page.screenshot({
      path: outputPng,
      fullPage: false,
      clip: { x: 0, y: 0, width: parseInt(width), height: parseInt(height) },
    });
    console.log(`PNG salvo: ${outputPng}`);
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
