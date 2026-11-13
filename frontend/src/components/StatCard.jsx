export default function StatCard({ label, value, sublabel, tone = "default" }) {
  const toneClass = {
    default: "text-textprimary",
    good: "text-accentgreen",
    warn: "text-accentamber",
    bad: "text-accentred",
  }[tone];

  return (
    <div className="rounded-lg border border-panelborder bg-panel p-4">
      <div className="text-xs text-textmuted mb-1">{label}</div>
      <div className={`text-2xl font-semibold ${toneClass}`}>{value}</div>
      {sublabel && <div className="text-xs text-textmuted mt-1">{sublabel}</div>}
    </div>
  );
}
