import { chromium } from "../../frontend/node_modules/playwright/index.mjs";
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
const app = "http://localhost:8083";
const artifacts = new URL("./artifacts/", import.meta.url);
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ headless: true });
const failures = [],
  checked = [];
const plans = {
  customer: [
    "dashboard",
    "parcels",
    "book",
    "support",
    "addresses",
    "notifications",
    "stations",
    "profile",
  ],
  rider: [
    "dashboard",
    "parcels",
    "tasks",
    "onboarding",
    "earnings",
    "queue",
    "support",
    "notifications",
    "stations",
    "profile",
  ],
  carrier: [
    "dashboard",
    "parcels",
    "tasks",
    "onboarding",
    "earnings",
    "trips",
    "queue",
    "support",
    "notifications",
    "stations",
    "profile",
  ],
  station_operator: [
    "dashboard",
    "parcels",
    "book",
    "trips",
    "partners",
    "earnings",
    "audit",
    "stations",
    "support",
    "notifications",
    "profile",
  ],
  ops: [
    "dashboard",
    "parcels",
    "book",
    "trips",
    "partners",
    "payments",
    "payouts",
    "rates",
    "reports",
    "audit",
    "finance-audit",
    "cities",
    "stations",
    "support",
    "notifications",
    "profile",
  ],
  finance: [
    "dashboard",
    "parcels",
    "payments",
    "payouts",
    "rates",
    "reports",
    "finance-audit",
    "support",
    "notifications",
    "stations",
    "profile",
  ],
  support: [
    "dashboard",
    "parcels",
    "support",
    "notifications",
    "stations",
    "profile",
  ],
  admin: [
    "dashboard",
    "parcels",
    "book",
    "trips",
    "partners",
    "payments",
    "payouts",
    "rates",
    "reports",
    "audit",
    "finance-audit",
    "users",
    "settings",
    "cities",
    "stations",
    "support",
    "notifications",
    "profile",
  ],
};
try {
  for (const [role, screens] of Object.entries(plans)) {
    if (process.argv.includes("--booking")) continue;
    const selectedRole = process.argv
      .find((arg) => arg.startsWith("--role="))
      ?.split("=")[1];
    if (selectedRole && selectedRole !== role) continue;
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
    });
    const page = await context.newPage();
    const runtime = [];
    page.on("pageerror", (e) => runtime.push(e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error" && msg.text().includes("Unexpected text node"))
        runtime.push(msg.text());
    });
    await page.goto(app + "/login");
    await page.getByLabel("Username", { exact: true }).fill("demo_" + role);
    await page.getByLabel("Password", { exact: true }).fill("Demo123!");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL("**/workspace/dashboard");
    for (const screen of screens) {
      runtime.length = 0;
      await page.goto(app + "/workspace/" + screen);
      await page.waitForTimeout(600);
      const text = await page.locator("body").innerText();
      assert(
        !text.includes("This workspace is unavailable"),
        `${role}/${screen}: wrong role guard`,
      );
      const alerts = await page.getByRole("alert").allTextContents();
      if (
        alerts.length &&
        !(screen === "settings" && alerts.every((t) => t.includes("Not found")))
      )
        failures.push({ role, screen, alerts });
      checked.push(`${role}/${screen}`);
      if (runtime.length) {
        failures.push({ role, screen, runtime: [...runtime] });
        console.log("RENDER ERROR", role, screen);
      }
    }
    await page.screenshot({
      path: new URL(role + ".png", artifacts).pathname.replace(
        /^\/(\w:)/,
        "$1",
      ),
      fullPage: true,
    });
    await context.close();
    console.log(role, screens.length, "screens");
  }
  const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
    }),
    page = await context.newPage();
  await page.goto(app + "/login");
  await page.getByLabel("Username", { exact: true }).fill("demo_customer");
  await page.getByLabel("Password", { exact: true }).fill("Demo123!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL("**/workspace/dashboard");
  await page.goto(app + "/workspace/book");
  await page
    .getByRole("button", { name: "Drop-off station", exact: true })
    .click();
  await page.getByRole("button", { name: "Mutare Main", exact: true }).click();
  await page
    .getByRole("button", { name: "Destination station", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Chipinge Demo Parcel Point", exact: true })
    .click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page
    .getByLabel("Recipient full name", { exact: true })
    .fill("Mobile Acceptance Recipient");
  await page
    .getByLabel("Recipient phone", { exact: true })
    .fill("+263779123456");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Choose photo", exact: true }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({
    name: "parcel.png",
    mimeType: "image/png",
    buffer: await page.screenshot(),
  });
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  const createdPromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/parcels/") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Confirm booking", exact: true })
    .click();
  const created = await createdPromise;
  assert.equal(created.status(), 201, await created.text());
  const parcel = await created.json();
  try {
    await page.waitForURL("**/parcel/*");
  } catch (error) {
    console.log(await page.locator("body").innerText());
    throw error;
  }
  checked.push("UC05 customer booking with photo and quote");
  await page.screenshot({
    path: new URL("booked.png", artifacts).pathname.replace(/^\/(\w:)/, "$1"),
    fullPage: true,
  });
  await context.close();
  const guest = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const recipient = await guest.newPage();
  await recipient.goto(app + "/track/" + parcel.recipient_access_token);
  await recipient.getByText(parcel.code, { exact: false }).first().waitFor();
  assert.equal(await recipient.getByRole("alert").count(), 0);
  checked.push("UC15 guest private tracking without sign-in");
  await recipient
    .getByRole("button", { name: "Change receiving preference", exact: true })
    .click();
  await recipient
    .getByRole("button", { name: "Receiving method", exact: true })
    .click();
  await recipient.getByRole("button", { name: "home", exact: true }).click();
  await recipient
    .getByLabel("Home address", { exact: true })
    .fill("Acceptance address, Chipinge");
  await recipient.getByRole("button", { name: "Confirm", exact: true }).click();
  await recipient.getByRole("button", { name: "Done", exact: true }).waitFor();
  await recipient.getByRole("button", { name: "Done", exact: true }).click();
  await recipient
    .getByText("Acceptance address, Chipinge", { exact: false })
    .first()
    .waitFor();
  checked.push("UC15 guest home-delivery preference saved");
  await guest.close();
} catch (error) {
  failures.push({ error: error.stack });
  console.error(error);
} finally {
  await browser.close();
  await writeFile(
    new URL("acceptance.json", artifacts),
    JSON.stringify({ checked, failures }, null, 2),
  );
}
assert.equal(failures.length, 0, JSON.stringify(failures, null, 2));
console.log("PASS", checked.length, "checks");
