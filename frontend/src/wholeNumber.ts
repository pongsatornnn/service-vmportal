import type React from "react";

// Number inputs that only ever hold whole numbers: no decimals, exponents or signs.
export const wholeNumber = {
  type: "number",
  step: 1,
  inputMode: "numeric" as const,
  onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => {
    if ([".", ",", "e", "E", "+", "-"].includes(e.key)) e.preventDefault();
  },
  onPaste: (e: React.ClipboardEvent<HTMLInputElement>) => {
    if (!/^\d+$/.test(e.clipboardData.getData("text").trim())) e.preventDefault();
  },
};
