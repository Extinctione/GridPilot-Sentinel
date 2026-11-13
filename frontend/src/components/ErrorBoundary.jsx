import { Component } from "react";

// Catches JS render-time errors in whatever it wraps (a bad data shape, a
// bug in a chart, etc.) and shows a contained error message instead of
// letting the whole dashboard go blank. This is distinct from the
// ErrorState component: ErrorState handles *expected* API failures inside
// a page's own render logic, while this handles *unexpected* exceptions
// thrown during render that no amount of if/else in the page could catch.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("Dashboard module crashed:", error, info);
  }

  handleRetry = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-lg border border-accentred/40 bg-accentred/10 p-4 text-sm text-accentred max-w-2xl space-y-2">
          <div className="font-medium">This module hit an unexpected error and couldn't render.</div>
          <div className="text-xs opacity-80 font-mono break-all">{String(this.state.error.message || this.state.error)}</div>
          <button
            onClick={this.handleRetry}
            className="rounded-md border border-accentred/50 px-3 py-1 text-xs hover:bg-accentred/20"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
