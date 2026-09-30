/**
 * Tests for the <GcSignature> Government of Canada signature: a
 * decorative svg with the FIP-red flag and theme-following wordmark.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GcSignature } from "@/components/Header/GcSignature";

describe("GcSignature", () => {
  it("renders a decorative svg hidden from assistive tech", () => {
    render(<GcSignature />);
    const svg = screen.getByTestId("gc-signature");
    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("viewBox", "0 0 819 75.97");
  });

  it("keeps the official aspect ratio for the requested height", () => {
    render(<GcSignature height={26} />);
    const svg = screen.getByTestId("gc-signature");
    expect(svg).toHaveAttribute("height", "26");
    expect(svg).toHaveAttribute("width", "280");
  });

  it("paints the flag in FIP red and the bilingual wordmark in currentColor", () => {
    render(<GcSignature />);
    const fills = Array.from(
      screen.getByTestId("gc-signature").querySelectorAll("path"),
    ).map((el) => el.getAttribute("fill"));
    expect(fills).toEqual(["#EB2D37", "currentColor", "currentColor"]);
  });
});
