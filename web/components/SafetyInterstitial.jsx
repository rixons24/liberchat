"use client";

import { useState } from "react";

const POINTS = [
  { code: "01", text: "You must be 18 or older." },
  { code: "02", text: "Identities are not verified. Treat every stranger as unverified." },
  { code: "03", text: "Meeting in person is your decision and your risk. Meet public, tell a friend." },
  { code: "04", text: "Report anything uncomfortable in two taps. Safety reports are reviewed first." },
  { code: "05", text: "Zero tolerance for harm to minors. Reported to law enforcement, no exceptions." },
];

export default function SafetyInterstitial({ onAccept }) {
  const [checked, setChecked] = useState(false);

  return (
    <main className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="panel max-w-md w-full p-6 flex flex-col gap-5">
        <span className="label">Read before continuing</span>

        <div className="flex flex-col gap-3">
          {POINTS.map((p) => (
            <div key={p.code} className="flex gap-3 items-start">
              <span className="font-mono text-xs text-accent pt-1">{p.code}</span>
              <p className="text-[14px] leading-relaxed text-ink">{p.text}</p>
            </div>
          ))}
        </div>

        <label className="flex items-center gap-3 pt-4 border-t border-line cursor-pointer">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            className="w-4 h-4"
          />
          <span className="text-[13px] text-muted">
            I confirm I am 18 or older and agree to the Community Guidelines.
          </span>
        </label>

        <button
          disabled={!checked}
          onClick={onAccept}
          className="btn-primary disabled:opacity-40"
        >
          Continue
        </button>
      </div>
    </main>
  );
}
