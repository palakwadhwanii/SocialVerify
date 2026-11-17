import PDFDocument from "pdfkit";

type ReportMessage = {
  sender: string;
  content: string | null;
  createdAt: unknown;
};

const colors = {
  accent: "#236c4b",
  accentLight: "#eaf2ed",
  ink: "#17201b",
  body: "#354139",
  muted: "#748078",
  rule: "#dce5de",
  soft: "#f5f8f5",
  white: "#ffffff",
};

const copy = {
  brand: "SOCIALVERIFY",
  subtitle: "MULTI-AGENT FACT VERIFICATION & DIVERGENCE ANALYSIS",
  document: "Verified Investigation Report",
};

const page = {
  left: 56,
  right: 56,
  top: 88,
  bottom: 62,
};

function cleanMarkdown(value: string) {
  return value
    .replace(/<!-- socialverify-investigation:v1:[\s\S]*?-->/g, "")
    .replace(/<!-- socialverify-graph-slot -->/g, "")
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(\*|_)(.*?)\1/g, "$2")
    .replace(/~~(.*?)~~/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

function isTableRow(line: string) {
  return line.trim().startsWith("|") && line.trim().endsWith("|");
}

function tableCells(line: string) {
  return line
    .trim()
    .slice(1, -1)
    .split("|")
    .map((cell) => cleanMarkdown(cell.trim()));
}

function lineAt(lines: string[], index: number) {
  const line = lines[index];
  if (line === undefined) {
    throw new RangeError(`Markdown line index ${index} is out of bounds.`);
  }
  return line;
}

export function createResearchPdf(title: string | null, messages: ReportMessage[]) {
  return new Promise<Buffer>((resolve, reject) => {
    const reportTitle = title?.trim() || copy.document;
    const generatedAt = new Date();
    const document = new PDFDocument({
      size: "A4",
      margins: {
        top: page.top,
        bottom: page.bottom,
        left: page.left,
        right: page.right,
      },
      bufferPages: true,
      info: {
        Title: reportTitle,
        Author: copy.brand,
        Subject: copy.document,
        CreationDate: generatedAt,
      },
    });

    const chunks: Buffer[] = [];
    document.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    document.on("end", () => resolve(Buffer.concat(chunks)));
    document.on("error", reject);

    const contentWidth = document.page.width - page.left - page.right;
    const contentBottom = () => document.page.height - page.bottom;

    function drawHeader() {
      const currentY = document.y;
      document.save();
      document.rect(0, 0, document.page.width, 7).fill(colors.accent);
      document
        .font("Helvetica-Bold")
        .fontSize(9)
        .fillColor(colors.accent)
        .text(copy.brand, page.left, 29, {
          width: 150,
          lineBreak: false,
          characterSpacing: 1.5,
        });
      document
        .font("Helvetica")
        .fontSize(6.5)
        .fillColor(colors.muted)
        .text(copy.subtitle, page.left, 43, {
          width: 340,
          lineBreak: false,
          characterSpacing: 0.35,
        });
      document
        .font("Helvetica")
        .fontSize(7)
        .fillColor(colors.muted)
        .text("VERIFIED RESEARCH BRIEF", document.page.width - page.right - 170, 30, {
          width: 170,
          align: "right",
          lineBreak: false,
          characterSpacing: 0.8,
        });
      document
        .strokeColor(colors.rule)
        .lineWidth(0.7)
        .moveTo(page.left, 63)
        .lineTo(document.page.width - page.right, 63)
        .stroke();
      document.restore();
      document.y = currentY;
    }

    document.on("pageAdded", drawHeader);
    drawHeader();

    function ensureSpace(height: number) {
      if (document.y + height > contentBottom()) {
        document.addPage();
      }
    }

    function addSpace(height: number) {
      document.y += height;
      if (document.y > contentBottom()) document.addPage();
    }

    function drawInquiry(text: string, label: string) {
      const cleanText = cleanMarkdown(text || "Investigation query");
      document.font("Helvetica").fontSize(10);
      const textHeight = document.heightOfString(cleanText, {
        width: contentWidth - 32,
        lineGap: 2,
      });
      const boxHeight = Math.max(62, textHeight + 42);
      ensureSpace(boxHeight + 12);
      const boxY = document.y;

      document.save();
      document.roundedRect(page.left, boxY, contentWidth, boxHeight, 5).fill(colors.soft);
      document.rect(page.left, boxY, 4, boxHeight).fill(colors.accent);
      document
        .font("Helvetica-Bold")
        .fontSize(7.5)
        .fillColor(colors.accent)
        .text(label, page.left + 16, boxY + 11, {
          width: contentWidth - 32,
          characterSpacing: 0.8,
        });
      document
        .font("Helvetica")
        .fontSize(10)
        .fillColor(colors.ink)
        .text(cleanText, page.left + 16, boxY + 27, {
          width: contentWidth - 32,
          lineGap: 2,
        });
      document.restore();
      document.y = boxY + boxHeight + 12;
    }

    function drawHeading(text: string, level: number) {
      const heading = cleanMarkdown(text);
      const fontSize = level === 1 ? 17 : level === 2 ? 13 : 10.5;
      const topGap = level === 1 ? 13 : 10;
      document.font("Helvetica-Bold").fontSize(fontSize);
      const headingHeight = document.heightOfString(heading, { width: contentWidth });
      ensureSpace(headingHeight + topGap + 9);
      addSpace(topGap);
      const headingY = document.y;
      document.fillColor(level === 2 ? colors.accent : colors.ink).text(heading, {
        width: contentWidth,
        lineGap: 2,
      });
      if (level === 2) {
        document
          .strokeColor(colors.rule)
          .lineWidth(0.6)
          .moveTo(page.left, document.y + 3)
          .lineTo(page.left + contentWidth, document.y + 3)
          .stroke();
      }
      document.y = Math.max(document.y, headingY + headingHeight) + 5;
    }

    function drawParagraph(text: string) {
      const paragraph = cleanMarkdown(text);
      if (!paragraph) return;
      document.font("Helvetica").fontSize(9.5);
      const height = document.heightOfString(paragraph, {
        width: contentWidth,
        lineGap: 3,
      });
      ensureSpace(Math.min(height, contentBottom() - page.top) + 8);
      document.fillColor(colors.body).text(paragraph, {
        width: contentWidth,
        lineGap: 3,
        paragraphGap: 0,
      });
      addSpace(7);
    }

    function drawBullet(text: string, indexLabel?: string) {
      const bullet = cleanMarkdown(text);
      document.font("Helvetica").fontSize(9.5);
      const textWidth = contentWidth - 25;
      const height = document.heightOfString(bullet, {
        width: textWidth,
        lineGap: 2,
      });
      ensureSpace(Math.min(height, contentBottom() - page.top) + 5);
      const startY = document.y;
      document
        .font("Helvetica-Bold")
        .fontSize(9)
        .fillColor(colors.accent)
        .text(indexLabel ?? "•", page.left + 3, startY, { width: 17 });
      document
        .font("Helvetica")
        .fontSize(9.5)
        .fillColor(colors.body)
        .text(bullet, page.left + 22, startY, {
          width: textWidth,
          lineGap: 2,
        });
      addSpace(4);
    }

    function drawQuote(text: string) {
      const quote = cleanMarkdown(text);
      document.font("Helvetica-Oblique").fontSize(9.5);
      const height = document.heightOfString(quote, {
        width: contentWidth - 32,
        lineGap: 3,
      });
      const boxHeight = height + 20;
      ensureSpace(Math.min(boxHeight, contentBottom() - page.top) + 8);
      const startY = document.y;
      document.save();
      document.roundedRect(page.left, startY, contentWidth, boxHeight, 4).fill(colors.soft);
      document.rect(page.left, startY, 3, boxHeight).fill(colors.accent);
      document
        .font("Helvetica-Oblique")
        .fontSize(9.5)
        .fillColor(colors.body)
        .text(quote, page.left + 15, startY + 10, {
          width: contentWidth - 30,
          lineGap: 3,
        });
      document.restore();
      document.y = startY + boxHeight + 8;
    }

    function drawCode(lines: string[]) {
      const code = lines.join("\n");
      document.font("Courier").fontSize(8);
      const height = document.heightOfString(code, {
        width: contentWidth - 24,
        lineGap: 2,
      });
      const boxHeight = Math.min(height + 18, contentBottom() - page.top);
      ensureSpace(boxHeight + 8);
      const startY = document.y;
      document.save();
      document.roundedRect(page.left, startY, contentWidth, boxHeight, 4).fill(colors.soft);
      document
        .font("Courier")
        .fontSize(8)
        .fillColor(colors.body)
        .text(code, page.left + 12, startY + 9, {
          width: contentWidth - 24,
          lineGap: 2,
          height: boxHeight - 14,
          ellipsis: true,
        });
      document.restore();
      document.y = startY + boxHeight + 8;
    }

    function drawTable(rows: string[][]) {
      const columnCount = Math.max(...rows.map((row) => row.length));
      const cellPaddingX = 7;
      const cellPaddingY = 6;
      const columnWidth = contentWidth / columnCount;

      rows.forEach((row, rowIndex) => {
        const cells = Array.from({ length: columnCount }, (_, index) =>
          row[index] ?? "",
        );
        document.font(rowIndex === 0 ? "Helvetica-Bold" : "Helvetica").fontSize(7.5);
        const heights = cells.map((cell) =>
          document.heightOfString(cell, {
            width: columnWidth - cellPaddingX * 2,
            lineGap: 1,
          }),
        );
        const rowHeight = Math.max(26, ...heights.map((height) => height + cellPaddingY * 2));
        ensureSpace(Math.min(rowHeight, contentBottom() - page.top) + 4);
        const rowY = document.y;
        document.save();
        document
          .rect(page.left, rowY, contentWidth, rowHeight)
          .fill(rowIndex === 0 ? colors.accentLight : rowIndex % 2 ? colors.white : colors.soft);

        cells.forEach((cell, cellIndex) => {
          const x = page.left + cellIndex * columnWidth;
          if (cellIndex > 0) {
            document
              .strokeColor(colors.rule)
              .lineWidth(0.5)
              .moveTo(x, rowY)
              .lineTo(x, rowY + rowHeight)
              .stroke();
          }
          document
            .font(rowIndex === 0 ? "Helvetica-Bold" : "Helvetica")
            .fontSize(7.5)
            .fillColor(rowIndex === 0 ? colors.accent : colors.body)
            .text(cell, x + cellPaddingX, rowY + cellPaddingY, {
              width: columnWidth - cellPaddingX * 2,
              lineGap: 1,
              height: rowHeight - cellPaddingY * 2,
              ellipsis: true,
            });
        });
        document
          .strokeColor(colors.rule)
          .lineWidth(0.5)
          .rect(page.left, rowY, contentWidth, rowHeight)
          .stroke();
        document.restore();
        document.y = rowY + rowHeight;
      });
      addSpace(8);
    }

    const generatedLabel = generatedAt.toLocaleString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
    document.y = page.top;
    document.font("Helvetica-Bold").fontSize(22).fillColor(colors.ink);
    const titleHeight = document.heightOfString(reportTitle, {
      width: contentWidth,
      lineGap: 2,
    });
    ensureSpace(titleHeight + 44);
    document.text(reportTitle, { width: contentWidth, lineGap: 2 });
    document.y += 8;
    document
      .font("Helvetica")
      .fontSize(8)
      .fillColor(colors.muted)
      .text(`Generated ${generatedLabel}   ·   ${messages.length} conversation messages`, {
        width: contentWidth,
      });
    document.y += 15;

    const firstInquiry = messages.find((message) => message.sender === "user");
    if (firstInquiry) drawInquiry(firstInquiry.content ?? "", "INVESTIGATION QUESTION");

    document
      .font("Helvetica-Bold")
      .fontSize(8)
      .fillColor(colors.accent)
      .text("VERIFIED BRIEF & DIVERGENCE REPORT", {
        width: contentWidth,
        characterSpacing: 0.8,
      });
    document.y += 10;

    let inquiryCount = 0;
    for (const message of messages) {
      if (message.sender === "user") {
        inquiryCount += 1;
        if (message !== firstInquiry) {
          drawInquiry(message.content ?? "", `FOLLOW-UP QUESTION ${inquiryCount}`);
        }
        continue;
      }
      if (!message.content?.trim()) continue;

      const lines = message.content.replace(/\r\n?/g, "\n").split("\n");
      for (let index = 0; index < lines.length;) {
        const line = lineAt(lines, index).trim();
        if (!line) {
          index += 1;
          continue;
        }
        if (/^```/.test(line)) {
          const codeLines: string[] = [];
          index += 1;
          while (index < lines.length && !/^```/.test(lineAt(lines, index).trim())) {
            codeLines.push(lineAt(lines, index));
            index += 1;
          }
          index += 1;
          if (codeLines.length) drawCode(codeLines);
          continue;
        }
        const heading = line.match(/^(#{1,3})\s+(.+)$/);
        const headingMarks = heading?.[1];
        const headingText = heading?.[2];
        if (headingMarks && headingText) {
          drawHeading(headingText, headingMarks.length);
          index += 1;
          continue;
        }
        if (/^>\s?/.test(line)) {
          const quoteLines: string[] = [];
          while (index < lines.length && /^>\s?/.test(lineAt(lines, index).trim())) {
            quoteLines.push(lineAt(lines, index).trim().replace(/^>\s?/, ""));
            index += 1;
          }
          drawQuote(quoteLines.join(" "));
          continue;
        }
        if (isTableRow(line)) {
          const rows: string[][] = [];
          while (index < lines.length && isTableRow(lineAt(lines, index))) {
            const cells = tableCells(lineAt(lines, index));
            if (!cells.every((cell) => /^:?-{3,}:?$/.test(cell))) rows.push(cells);
            index += 1;
          }
          if (rows.length) drawTable(rows);
          continue;
        }
        const unordered = line.match(/^[-*+]\s+(.+)$/);
        const ordered = line.match(/^\d+[.)]\s+(.+)$/);
        if (unordered || ordered) {
          const listPattern = unordered ? /^[-*+]\s+/ : /^\d+[.)]\s+/;
          let listNumber = 1;
          while (
            index < lines.length &&
            listPattern.test(lineAt(lines, index).trim())
          ) {
            const item = lineAt(lines, index).trim().replace(listPattern, "");
            drawBullet(item, ordered ? `${listNumber}.` : undefined);
            listNumber += 1;
            index += 1;
          }
          continue;
        }
        if (/^---+$/.test(line)) {
          ensureSpace(12);
          document
            .strokeColor(colors.rule)
            .lineWidth(0.7)
            .moveTo(page.left, document.y + 4)
            .lineTo(page.left + contentWidth, document.y + 4)
            .stroke();
          addSpace(13);
          index += 1;
          continue;
        }

        const paragraphLines = [line];
        index += 1;
        while (
          index < lines.length &&
          lineAt(lines, index).trim() &&
          !/^(#{1,3})\s+/.test(lineAt(lines, index).trim()) &&
          !/^>\s?/.test(lineAt(lines, index).trim()) &&
          !isTableRow(lineAt(lines, index)) &&
          !/^[-*+]\s+/.test(lineAt(lines, index).trim()) &&
          !/^\d+[.)]\s+/.test(lineAt(lines, index).trim()) &&
          !/^```/.test(lineAt(lines, index).trim()) &&
          !/^---+$/.test(lineAt(lines, index).trim())
        ) {
          paragraphLines.push(lineAt(lines, index).trim());
          index += 1;
        }
        drawParagraph(paragraphLines.join(" "));
      }
    }

    const pageRange = document.bufferedPageRange();
    for (let index = pageRange.start; index < pageRange.start + pageRange.count; index += 1) {
      document.switchToPage(index);
      const footerY = document.page.height - 37;
      document
        .strokeColor(colors.rule)
        .lineWidth(0.7)
        .moveTo(page.left, footerY - 10)
        .lineTo(document.page.width - page.right, footerY - 10)
        .stroke();
      document
        .font("Helvetica")
        .fontSize(7)
        .fillColor(colors.muted)
        .text("SOCIALVERIFY  ·  VERIFIED INVESTIGATION REPORT", page.left, footerY, {
          width: contentWidth - 55,
          lineBreak: false,
          characterSpacing: 0.4,
        });
      document
        .font("Helvetica")
        .fontSize(7)
        .fillColor(colors.muted)
        .text(`${index - pageRange.start + 1} / ${pageRange.count}`, page.left, footerY, {
          width: contentWidth,
          align: "right",
          lineBreak: false,
        });
    }

    document.end();
  });
}
