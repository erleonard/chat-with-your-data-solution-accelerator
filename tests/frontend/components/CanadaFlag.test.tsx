/**
 * Tests for the <CanadaFlag> brand mark: a decorative 2:1 svg with the
 * red-white-red bands and the red maple leaf.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CanadaFlag } from "@/components/Header/CanadaFlag";

describe("CanadaFlag", () => {
  it("renders a decorative svg hidden from assistive tech", () => {
    render(<CanadaFlag />);
    const svg = screen.getByTestId("canada-flag");
    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("viewBox", "0 0 9600 4800");
  });

  it("keeps the 2:1 flag ratio for the requested height", () => {
    render(<CanadaFlag height={18} />);
    const svg = screen.getByTestId("canada-flag");
    expect(svg).toHaveAttribute("height", "18");
    expect(svg).toHaveAttribute("width", "36");
  });

  it("paints the red bands, white pale, and red maple leaf", () => {
    render(<CanadaFlag />);
    const svg = screen.getByTestId("canada-flag");
    const fills = Array.from(svg.querySelectorAll("rect, path")).map((el) =>
      el.getAttribute("fill"),
    );
    expect(fills).toEqual(["#d52b1e", "#ffffff", "#d52b1e"]);
  });
});
