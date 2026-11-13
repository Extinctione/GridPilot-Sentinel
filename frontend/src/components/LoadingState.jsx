export default function LoadingState({ label = "Loading..." }) {
  return (
    <div className="flex items-center gap-2 text-sm text-textmuted py-8">
      <span className="h-2 w-2 rounded-full bg-textmuted animate-pulse" />
      {label}
    </div>
  );
}
