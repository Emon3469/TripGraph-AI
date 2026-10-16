"use client";

import { useState } from "react";
import { Check, PencilLine, Send } from "lucide-react";

export default function ReviewBar({
  disabled,
  onReview,
}: {
  disabled: boolean;
  onReview: (approved: boolean, feedback?: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [feedback, setFeedback] = useState("");

  const submit = () => {
    if (!feedback.trim()) return;
    onReview(false, feedback);
    setFeedback("");
    setEditing(false);
  };

  return (
    <div className="mt-3 animate-fade-up rounded-2xl border border-brand-100 bg-brand-50/60 p-3">
      <p className="text-[12.5px] font-medium text-ink-700">
        Happy with this draft? Approve it for the final plan, or tell me what to change.
      </p>
      {editing ? (
        <div className="mt-2.5 flex items-end gap-2">
          <textarea
            autoFocus
            rows={2}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="e.g. Swap day 2 for a day trip to Malacca and keep it under $900"
            className="min-h-[44px] flex-1 resize-none rounded-xl border border-ink-200 bg-white px-3 py-2 text-[13px] outline-none focus:border-brand-300 focus:ring-2 focus:ring-brand-100"
          />
          <button
            type="button"
            disabled={disabled || !feedback.trim()}
            onClick={submit}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-ink-900 text-white transition disabled:opacity-40"
            aria-label="Send changes"
          >
            <Send size={15} />
          </button>
        </div>
      ) : (
        <div className="mt-2.5 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={disabled}
            onClick={() => onReview(true)}
            className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-brand-400 to-brand-600 px-4 py-2 text-[12.5px] font-semibold text-white shadow-brand transition hover:brightness-105 disabled:opacity-50"
          >
            <Check size={14} strokeWidth={2.5} /> Approve plan
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => setEditing(true)}
            className="inline-flex items-center gap-1.5 rounded-full border border-ink-200 bg-white px-4 py-2 text-[12.5px] font-semibold text-ink-700 transition hover:bg-ink-50 disabled:opacity-50"
          >
            <PencilLine size={14} /> Request changes
          </button>
        </div>
      )}
    </div>
  );
}
