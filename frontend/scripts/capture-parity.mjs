import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const base = process.env.CINEFORGE_UI_BASE || 'http://127.0.0.1:4173'
const outDir = process.env.CINEFORGE_SHOT_DIR
if (!outDir) {
  console.error('CINEFORGE_SHOT_DIR required')
  process.exit(1)
}

const routes = [
  { id: 'overview', route: 'overview', source: 'Screenshot 2026-07-11 172715.png' },
  { id: 'storyboard', route: 'storyboard', source: 'Screenshot 2026-07-11 172722.png' },
  { id: 'story', route: 'story', source: 'Screenshot 2026-07-11 172730.png' },
  { id: 'characters', route: 'characters', source: 'Screenshot 2026-07-11 172736.png' },
  { id: 'voices', route: 'voices', source: 'Screenshot 2026-07-11 172742.png' },
  { id: 'images', route: 'starting-images', source: 'Screenshot 2026-07-11 172748.png' },
  { id: 'routing', route: 'model-routing', source: 'Screenshot 2026-07-11 172754.png' },
  { id: 'workflows', route: 'workflows', source: 'Screenshot 2026-07-11 172759.png' },
  { id: 'exports', route: 'exports', source: 'Screenshot 2026-07-11 172805.png' },
  { id: 'settings', route: 'settings', source: '(prototype SettingsPage — no dedicated screenshot)' },
]

const projectId = 'a-new-journey'
const consoleErrors = []

await mkdir(outDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
})
const page = await context.newPage()
page.on('pageerror', (err) => consoleErrors.push(String(err)))
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(msg.text())
})

const results = []

async function capture(name, viewport) {
  await page.setViewportSize(viewport)
  await page.waitForTimeout(400)
  const file = path.join(outDir, name)
  await page.screenshot({ path: file, fullPage: false })
  return file
}

// Landing + canonicalize
await page.goto(`${base}/`, { waitUntil: 'networkidle', timeout: 60000 })
await page.waitForTimeout(800)

for (const item of routes) {
  const url = `${base}/projects/${projectId}/studio/${item.route}`
  const entry = {
    id: item.id,
    source: item.source,
    route: `/projects/${projectId}/studio/${item.route}`,
    url,
    nav: 'pending',
    active: 'pending',
    deepLink: 'pending',
    reload: 'pending',
    overflow: 'pending',
    implemented: null,
    responsive390: null,
    responsive768: null,
    parity: 'PARTIAL',
    notes: [],
  }

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 })
    await page.waitForTimeout(700)
    entry.deepLink = 'PASS'

    // Active nav: look for aria-current=page
    const activeText = await page.locator('nav[aria-label="Primary navigation"] button[aria-current="page"], .settings-entry[aria-current="page"]').first().innerText().catch(() => '')
    entry.active = activeText ? `PASS (${activeText.replace(/\s+/g, ' ').trim()})` : 'WARN (no aria-current)'

    // Horizontal overflow
    const overflow = await page.evaluate(() => {
      const doc = document.documentElement
      return doc.scrollWidth > doc.clientWidth + 1
    })
    entry.overflow = overflow ? 'FAIL' : 'PASS'

    entry.implemented = await capture(`${item.id}-1440x900.png`, { width: 1440, height: 900 })

    // Sidebar click from overview-ish: navigate via nav button
    const navLabel =
      item.id === 'story'
        ? 'Story'
        : item.id === 'images'
          ? 'Starting'
          : item.id === 'routing'
            ? 'Model'
            : item.id === 'settings'
              ? 'Project settings'
              : item.id.charAt(0).toUpperCase() + item.id.slice(1)
    // Go to overview first then click
    await page.goto(`${base}/projects/${projectId}/studio/overview`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(300)
    const clicked = await page
      .locator('aside button, nav button')
      .filter({ hasText: new RegExp(navLabel, 'i') })
      .first()
      .click({ timeout: 5000 })
      .then(() => true)
      .catch(() => false)
    await page.waitForTimeout(500)
    entry.nav = clicked ? 'PASS' : 'WARN (click miss)'

    // Reload current
    await page.goto(url, { waitUntil: 'networkidle' })
    await page.reload({ waitUntil: 'networkidle' })
    await page.waitForTimeout(400)
    entry.reload = page.url().includes(item.route) || page.url().includes(item.id) ? 'PASS' : 'WARN'

    // Responsive samples for first three + settings
    if (['overview', 'storyboard', 'characters', 'settings'].includes(item.id)) {
      await page.goto(url, { waitUntil: 'networkidle' })
      entry.responsive390 = await capture(`${item.id}-390x844.png`, { width: 390, height: 844 })
      entry.responsive768 = await capture(`${item.id}-768x1024.png`, { width: 768, height: 1024 })
    }

    entry.parity =
      entry.overflow === 'PASS' && entry.deepLink === 'PASS' ? 'PASS-VISUAL-REVIEW' : 'FAIL'
  } catch (error) {
    entry.parity = 'FAIL'
    entry.notes.push(String(error))
  }

  results.push(entry)
  console.log(JSON.stringify({ id: item.id, parity: entry.parity }))
}

// History smoke
await page.goto(`${base}/projects/${projectId}/studio/overview`, { waitUntil: 'networkidle' })
await page.goto(`${base}/projects/${projectId}/studio/storyboard`, { waitUntil: 'networkidle' })
await page.goBack()
await page.waitForTimeout(300)
const backOk = page.url().includes('overview')
await page.goForward()
await page.waitForTimeout(300)
const forwardOk = page.url().includes('storyboard')

const index = {
  base,
  outDir,
  capturedAt: new Date().toISOString(),
  history: { back: backOk ? 'PASS' : 'FAIL', forward: forwardOk ? 'PASS' : 'FAIL' },
  consoleErrors: consoleErrors.slice(0, 40),
  routes: results,
}

await writeFile(path.join(outDir, 'screenshot-index.json'), JSON.stringify(index, null, 2), 'utf8')

const md = [
  '# Screenshot index — Storyboard Phase A UI parity',
  '',
  `- Base: \`${base}\``,
  `- Captured: ${index.capturedAt}`,
  `- History back/forward: ${index.history.back} / ${index.history.forward}`,
  `- Console errors captured: ${consoleErrors.length}`,
  '',
  '| Route | Source screenshot | Implemented 1440×900 | Overflow | Deep link | Parity | Notes |',
  '|---|---|---|---|---|---|---|',
  ...results.map((r) =>
    `| ${r.id} | ${r.source} | \`${path.basename(r.implemented || '')}\` | ${r.overflow} | ${r.deepLink} | ${r.parity} | ${(r.notes || []).join('; ')} |`,
  ),
  '',
  '## Advisory-only differences',
  '- Density and chrome approximate prototype screenshots; some prototype mock metadata (fake installed models, fabricated workloads) intentionally omitted.',
  '- Demo plan used when backend unavailable; server remains canonical when reachable.',
  '- Settings has no dedicated original screenshot in the 10-image set.',
  '',
].join('\n')

await writeFile(path.join(outDir, 'screenshot-index.md'), md, 'utf8')
console.log(`INDEX=${path.join(outDir, 'screenshot-index.md')}`)
console.log(`ERRORS=${consoleErrors.length}`)

await browser.close()
process.exit(consoleErrors.length > 20 ? 1 : 0)
