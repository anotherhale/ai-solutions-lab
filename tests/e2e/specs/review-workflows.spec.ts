import { expect, test } from "@playwright/test";

test.describe("Wasatch review workbench", () => {
  test("approver records reply approval without a send control", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Inquiry").fill("tkt_0007");
    await page.getByRole("button", { name: "Open inquiry" }).click();
    await expect(
      page.getByText("We can be on site Thursday at 08:00 if you approve overtime."),
    ).toBeVisible();
    await expect(page.getByText("This reply has not been sent.")).toBeVisible();
    await expect(page.getByRole("button", { name: /send|deliver|email|sms/i })).toHaveCount(
      0,
    );
    await page.getByLabel("Decision note").fill("Overtime approved in browser e2e.");
    await page.getByRole("button", { name: "Approve reply" }).click();
    await expect(page.getByText("Approved. The message was not sent.")).toBeVisible();
  });

  test("approver accepts a document extraction without posting money", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Document extraction").fill("dx_0003");
    await page.getByRole("button", { name: "Open extraction" }).click();
    await expect(page.getByText(/invoice_number/)).toBeVisible();
    await page.getByLabel("Review note").fill("Vendor and invoice number match in e2e.");
    await page.getByRole("button", { name: "Accept extraction" }).click();
    await expect(
      page.getByText("Accepted. No invoice or payment was posted."),
    ).toBeVisible();
  });
});
