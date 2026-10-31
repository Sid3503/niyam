import { describe, expect, it } from "vitest";
import { titleFromFilename } from "@/lib/format";

describe("titleFromFilename", () => {
  it("turns a file name into a readable title and keeps dates intact", () => {
    expect(titleFromFilename("SEBI_2022-09-02_returns-claimed-by-unregulated-algo-platforms.pdf")).toBe("SEBI 2022-09-02 returns claimed by unregulated algo platforms");
    expect(titleFromFilename("proposal.docx")).toBe("proposal");
  });
});
