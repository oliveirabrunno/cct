/**
 * Renderiza HTML como PNG via Puppeteer.
 * Uso: node generators/screenshot.js <html_file> <output_png> [width] [height]
 */

const puppeteer = require("puppeteer");
const path = require("path");
const fs = require("fs");

async function main() {
  const [, , htmlFile, outputPng, width = "1080", height = "1080"] = process.argv;

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
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: parseInt(width), height: parseInt(height) });
  await page.goto(`file://${absoluteHtml}`, { waitUntil: "networkidle0" });

  // Aguarda fontes do Google Fonts carregarem
  await new Promise((r) => setTimeout(r, 1500));

  await page.screenshot({
    path: outputPng,
    fullPage: false,
    clip: { x: 0, y: 0, width: parseInt(width), height: parseInt(height) },
  });

  await browser.close();
  console.log(`PNG salvo: ${outputPng}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
