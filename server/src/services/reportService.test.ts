import { expect, test } from "bun:test";
import { createResearchPdf } from "./reportService";

test("creates a PDF research brief", async () => {
  const pdf = await createResearchPdf("AI regulation", [
    { sender: "user", content: "Compare coverage.", createdAt: new Date() },
    {
      sender: "bot",
      content:
        "# Finding\n\nSources **agree**.\n\n| Source | Finding |\n| --- | --- |\n| A | Supports the claim |",
      createdAt: new Date(),
    },
  ]);

  expect(pdf.subarray(0, 5).toString()).toBe("%PDF-");
  expect(pdf.length).toBeGreaterThan(1000);
});

test("adds page numbers and continues long briefs across pages", async () => {
  const content = Array.from(
    { length: 140 },
    (_, index) =>
      `## Evidence section ${index + 1}\n\n` +
      "Multiple independent reports reviewed this claim and documented their source details.",
  ).join("\n\n");
  const pdf = await createResearchPdf("Long investigation", [
    { sender: "bot", content, createdAt: new Date() },
  ]);
  const pdfText = pdf.toString("latin1");
  const pageCount = (pdfText.match(/\/Type\s*\/Page\b/g) ?? []).length;

  expect(pageCount).toBeGreaterThan(1);
});
