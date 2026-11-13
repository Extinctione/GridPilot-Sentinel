export default function SeverityBadge({ severity }) {
  const map = {
    high: "bg-accentred/15 text-accentred border-accentred/40",
    medium: "bg-accentamber/15 text-accentamber border-accentamber/40",
    low: "bg-accentgreen/15 text-accentgreen border-accentgreen/40",
  };
  const cls = map[severity] || map.low;
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] uppercase tracking-wide ${cls}`}>
      {severity}
    </span>
  );
}
