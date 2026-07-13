"use client";

const EXAMPLES = [
  "How many PTO days do full-time employees get?",
  "What is the Nimbus API rate limit, and what happens when it's exceeded?",
  "Where in the cell does the Calvin cycle take place?",
  "What file size needs a multipart upload in Nimbus?",
];

export default function ExampleQuestions({
  onPick,
  disabled,
}: {
  onPick: (q: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {EXAMPLES.map((q) => (
        <button
          key={q}
          disabled={disabled}
          onClick={() => onPick(q)}
          className="text-left text-sm px-3 py-2 rounded-lg border border-ink-700 bg-ink-900/50 text-slate-300 hover:border-accent/50 hover:text-white transition-colors disabled:opacity-50"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
