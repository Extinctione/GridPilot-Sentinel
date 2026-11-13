export default function ErrorState({ message, onRetry }) {
  return (
    <div className="rounded-lg border border-accentred/40 bg-accentred/10 p-4 text-sm text-accentred flex items-center justify-between gap-4">
      <span>{message || "Something went wrong."}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 rounded-md border border-accentred/50 px-3 py-1 text-xs hover:bg-accentred/20"
        >
          Retry
        </button>
      )}
    </div>
  );
}
