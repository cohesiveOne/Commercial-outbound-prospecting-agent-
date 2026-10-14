#!/usr/bin/env node
// Build a Word review document from a processed run folder:
//   node scripts/report_docx.js output/runs/2026-10-14-data_center
// Reads meta.json, scored.json and dropped.json (written by `prospector process`)
// and writes <run_dir>/report.docx for sales review and draft approval.
const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, HeadingLevel, LevelFormat, Packer,
  PageBreak, PageNumber, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun,
  WidthType,
} = require("docx");

const runDir = process.argv[2];
if (!runDir) {
  console.error("usage: node scripts/report_docx.js <run_dir>");
  process.exit(2);
}
const read = (f, d) => {
  const p = path.join(runDir, f);
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf8")) : d;
};
const meta = read("meta.json", {});
const accountsForLabel = read("scored.json", []);
meta.segment_label = meta.segment_label || (accountsForLabel[0] || {}).segment_label;
const accounts = read("scored.json", []);
const dropped = read("dropped.json", []);

const BRAND = "E8380D";
const GRID = "BFBFBF";
const HEAD_FILL = "F2F2F2";
const TIER_FILL = { A: "E2F0D9", B: "FFF2CC", C: "F2F2F2" };
const CONTENT_WIDTH = 10080; // US Letter, 0.75" margins

const border = { style: BorderStyle.SINGLE, size: 4, color: GRID };
const borders = { top: border, bottom: border, left: border, right: border };

const text = (t, opts = {}) => new TextRun({ text: String(t ?? ""), ...opts });
const para = (children, opts = {}) =>
  new Paragraph({ children: Array.isArray(children) ? children : [children], ...opts });
const lines = (t, opts = {}) =>
  String(t || "").split("\n").map((l) => para(text(l, opts.run), { spacing: { after: 60 }, ...opts.para }));

function cell(content, width, { fill, bold } = {}) {
  const children = (Array.isArray(content) ? content : [content]).map((c) =>
    c instanceof Paragraph ? c : para(text(c, { bold, size: 18 })),
  );
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children,
  });
}

function table(widths, header, rows, rowFill) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({
        tableHeader: true,
        children: header.map((h, i) => cell(h, widths[i], { fill: HEAD_FILL, bold: true })),
      }),
      ...rows.map((r, ri) =>
        new TableRow({
          children: r.map((v, i) => cell(v, widths[i], { fill: rowFill ? rowFill(ri) : undefined })),
        }),
      ),
    ],
  });
}

const bullet = (t) => para(text(t), { numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 } });
const h1 = (t) => para(text(t), { heading: HeadingLevel.HEADING_1 });
const h2 = (t) => para(text(t), { heading: HeadingLevel.HEADING_2 });
const h3 = (t) => para(text(t), { heading: HeadingLevel.HEADING_3 });
const rule = () =>
  para(text(""), { border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: GRID, space: 1 } }, spacing: { after: 120 } });

const tiers = { A: 0, B: 0, C: 0 };
accounts.forEach((a) => (tiers[a.tier] = (tiers[a.tier] || 0) + 1));
const drafted = accounts.filter((a) => (a.outreach || []).length);
const issues = accounts.flatMap((a) => (a.draft_issues || []).map((i) => `${a.name}: ${i}`));

const body = [];

// ---------- Cover / summary
body.push(
  para(text("COHESIVE COMPONENTS · OUTBOUND PROSPECTING", { bold: true, color: BRAND, size: 18 }), { spacing: { after: 60 } }),
  para(text(`${meta.segment_label || meta.segment || "Prospecting run"} — Review & Approval`, { bold: true, size: 40 }), { spacing: { after: 120 } }),
  para([text("Run date: ", { bold: true }), text(meta.run_date || ""), text("    Prepared by: ", { bold: true }), text("Prospecting agent (draft only — nothing has been sent)")]),
  rule(),
  table(
    [2520, 2520, 2520, 2520],
    ["Accounts surfaced", "Tier A / B / C", "Accounts with drafts", "ZoomInfo credits used"],
    [[String(accounts.length), `${tiers.A || 0} / ${tiers.B || 0} / ${tiers.C || 0}`, `${drafted.length} (${drafted.reduce((n, a) => n + a.outreach.length, 0)} drafts)`, `${meta.credits_used ?? "n/a"} of ${meta.credit_cap ?? 60}`]],
  ),
  para(text(""), { spacing: { after: 120 } }),
  h2("How to review"),
  bullet("Skim the ranked table, then read each Tier A/B account section."),
  bullet("Under every draft, mark Approve, Edit or Reject and write any changes in the Notes line (or use Word comments / tracked changes)."),
  bullet("Return the marked-up file (or reply in chat). Approved drafts are loaded for the account owner to send from HubSpot."),
  bullet("Accounts already in HubSpot or ruled out are listed at the end with the reason."),
);
if (issues.length) {
  body.push(h2("⚠ Draft issues — fix before sending"), ...issues.map(bullet));
} else {
  body.push(para([text("Claim check: ", { bold: true }), text("all drafts passed (no banned terms, no unresolved placeholders).", { color: "2E7D32" })], { spacing: { before: 120 } }));
}

// ---------- Ranked table
body.push(para(new PageBreak()), h1("Ranked accounts"));
body.push(
  table(
    [400, 2000, 1850, 1080, 650, 550, 3550],
    ["#", "Account", "Sub-segment", "Employees", "Score", "Tier", "Why now"],
    accounts.map((a, i) => [
      String(i + 1),
      `${a.name}\n${a.domain || ""}`.split("\n").map((l, j) => para(text(l, { size: 18, bold: j === 0, color: j ? "595959" : undefined }))),
      a.sub_segment_label || "",
      a.employee_count ? Number(a.employee_count).toLocaleString("en-US") : "—",
      String(a.score),
      a.tier,
      a.why_now || "—",
    ]),
    (ri) => TIER_FILL[accounts[ri].tier],
  ),
);

// ---------- Account sections
accounts.forEach((a, idx) => {
  const detailed = a.tier !== "C" || (a.outreach || []).length || (a.contacts || []).length;
  if (!detailed) return;
  body.push(para(new PageBreak()));
  body.push(h1(`${a.name} — Tier ${a.tier} (${a.score})`));
  body.push(para([text(a.sub_segment_label || "", { italics: true }), text(`  ·  ${a.domain || ""}  ·  ${[a.city, a.state, a.country].filter(Boolean).join(", ")}`, { color: "595959" })]));
  body.push(para([text("Why now: ", { bold: true }), text(a.why_now || "no recent signal")], { spacing: { before: 120, after: 120 } }));
  const sigs = (a.signals || []).filter((s) => s.title);
  if (sigs.length) {
    body.push(h3("Evidence"));
    sigs.forEach((s) => body.push(bullet(`${s.date} — ${s.title}${s.url ? ` (${s.url})` : ""}`)));
  }
  body.push(h3("Why it fits"));
  (a.reasons || []).forEach((r) => body.push(bullet(r)));
  if ((a.applications || []).length) body.push(bullet(`Likely applications: ${a.applications.join(", ")}`));

  if ((a.contacts || []).length) {
    body.push(h3("Buying committee"));
    body.push(
      table(
        [2200, 3000, 1700, 3180],
        ["Name", "Title", "Role", "Email / phone"],
        a.contacts.map((c) => [
          `${c.first_name} ${c.last_name}`,
          c.title || "",
          c.persona_label || c.persona || "",
          [c.email, c.do_not_call ? "(do not call)" : c.phone].filter(Boolean).join("\n").split("\n").map((l) => para(text(l, { size: 18 }))),
        ]),
      ),
    );
  }

  (a.outreach || []).forEach((d) => {
    const ch = d.channel === "linkedin" ? "LinkedIn note" : `Email ${d.step}`;
    const day = { 1: "day 0", 2: "day 4", 3: "day 9" }[d.step];
    body.push(h3(`${ch}${d.channel === "linkedin" ? "" : ` (${day})`} → ${d.to}`));
    if (d.subject) body.push(para([text("Subject: ", { bold: true }), text(d.subject)], { spacing: { after: 80 } }));
    body.push(
      new Table({
        width: { size: CONTENT_WIDTH, type: WidthType.DXA },
        columnWidths: [CONTENT_WIDTH],
        rows: [new TableRow({ children: [new TableCell({
          borders: { top: border, bottom: border, right: border, left: { style: BorderStyle.SINGLE, size: 18, color: BRAND } },
          width: { size: CONTENT_WIDTH, type: WidthType.DXA },
          shading: { fill: "FAFAFA", type: ShadingType.CLEAR, color: "auto" },
          margins: { top: 120, bottom: 120, left: 200, right: 200 },
          children: lines(d.body),
        })] })],
      }),
    );
    body.push(para([text("☐ Approve    ☐ Edit    ☐ Reject     Notes: ", { bold: true, color: "404040" }), text("_______________________________________________", { color: "A6A6A6" })], { spacing: { before: 100, after: 240 } }));
  });
});

// ---------- Tier C without detail + dropped
const brief = accounts.filter((a) => a.tier === "C" && !(a.outreach || []).length && !(a.contacts || []).length);
body.push(para(new PageBreak()), h1("Other accounts and exclusions"));
if (brief.length) {
  body.push(h2("Tier C — kept for later (no contacts redeemed)"));
  brief.forEach((a) => body.push(bullet(`${a.name} (${a.domain}) — ${a.sub_segment_label}, score ${a.score}`)));
}
if (dropped.length) {
  body.push(h2("Dropped"));
  body.push(table([3000, 7080], ["Account", "Reason"], dropped.map((d) => [d.name || "", d.drop_reason || ""])));
}

const doc = new Document({
  creator: "Cohesive prospecting agent",
  title: `${meta.segment_label || "Prospecting"} review ${meta.run_date || ""}`,
  styles: {
    default: { document: { run: { font: "Calibri", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, color: "1F1F1F" }, paragraph: { spacing: { before: 120, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, color: BRAND }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 21, bold: true, color: "404040" }, paragraph: { spacing: { before: 180, after: 60 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] }],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } } },
    footers: { default: new Footer({ children: [para([
      text("Cohesive Components — internal, contains contact data. Draft only; not sent.   Page ", { size: 16, color: "808080" }),
      new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "808080" }),
    ], { alignment: AlignmentType.CENTER })] }) },
    children: body,
  }],
});

const out = path.join(runDir, "report.docx");
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(out, buf);
  console.log(out);
});
