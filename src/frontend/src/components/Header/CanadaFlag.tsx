/**
 * Inline SVG flag of Canada (2:1, red-white-red with the 11-point
 * maple leaf). Rendered as decorative brand chrome next to the header
 * wordmark; the enclosing home button carries the accessible name.
 */
import { type JSX } from "react";

export interface CanadaFlagProps {
  height?: number;
  className?: string;
}

const FLAG_RED = "#d52b1e";
const FLAG_WHITE = "#ffffff";

const MAPLE_LEAF_PATH =
  "M4890 4430l-45-863a95 95 0 0 1 111-98l859 151-116-320a65 65 0 0 1 20-73" +
  "l941-762-212-99a65 65 0 0 1-34-79l186-572-542 115a65 65 0 0 1-73-38" +
  "l-105-247-423 454a65 65 0 0 1-111-57l204-1052-327 189a65 65 0 0 1-91-27" +
  "l-332-652-332 652a65 65 0 0 1-91 27l-327-189 204 1052a65 65 0 0 1-111 57" +
  "l-423-454-105 247a65 65 0 0 1-73 38l-542-115 186 572a65 65 0 0 1-34 79" +
  "l-212 99 941 762a65 65 0 0 1 20 73l-116 320 859-151a95 95 0 0 1 111 98" +
  "l-45 863z";

export function CanadaFlag({
  height = 16,
  className,
}: CanadaFlagProps): JSX.Element {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 9600 4800"
      width={height * 2}
      height={height}
      aria-hidden="true"
      focusable="false"
      data-testid="canada-flag"
      className={className}
    >
      <rect width="9600" height="4800" fill={FLAG_RED} />
      <rect x="2400" width="4800" height="4800" fill={FLAG_WHITE} />
      <path d={MAPLE_LEAF_PATH} fill={FLAG_RED} />
    </svg>
  );
}
