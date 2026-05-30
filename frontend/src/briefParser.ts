export interface BriefSection {
  title: string;
  lines: string[];
}

export interface ParsedBrief {
  title: string;
  takeaway: string[];
  sections: BriefSection[];
  actions: BriefSection | null;
  metrics: BriefSection | null;
  sourceNotes: BriefSection | null;
}

const fallbackTitle = "Synthesis Brief";

export function parseBriefMarkdown(markdown: string): ParsedBrief {
  const sections: BriefSection[] = [];
  let title = fallbackTitle;
  let current: BriefSection | null = null;

  for (const rawLine of markdown.split("\n")) {
    const line = rawLine.trim();
    const heading = headingText(line);
    if (heading) {
      if (line.startsWith("# ") && title === fallbackTitle) {
        title = heading;
        current = null;
        continue;
      }
      current = { title: heading, lines: [] };
      sections.push(current);
      continue;
    }
    if (!current && line) {
      current = { title: "Summary", lines: [] };
      sections.push(current);
    }
    current?.lines.push(line);
  }

  const takeaway = sectionLines(sections, "Executive Takeaway");
  return {
    title,
    takeaway,
    sections: sections.filter((section) => section.title !== "Executive Takeaway"),
    actions: findSection(sections, "Recommended 30/60/90 Day Actions"),
    metrics: findSection(sections, "Metrics to Watch"),
    sourceNotes: findSection(sections, "Source Notes"),
  };
}

export function cleanMarkdown(value: string): string {
  return value.replace(/\*\*/g, "").replace(/`/g, "").trim();
}

export function presentableLines(lines: string[]): string[] {
  return lines
    .map((line) => cleanMarkdown(line.replace(/^[-*+]\s+/, "")))
    .filter(Boolean);
}

function headingText(line: string): string | null {
  const match = line.match(/^#{1,3}\s+(.+)$/);
  return match ? cleanMarkdown(match[1]) : null;
}

function findSection(sections: BriefSection[], title: string): BriefSection | null {
  return sections.find((section) => section.title === title) ?? null;
}

function sectionLines(sections: BriefSection[], title: string): string[] {
  const section = findSection(sections, title);
  return section ? presentableLines(section.lines) : [];
}
