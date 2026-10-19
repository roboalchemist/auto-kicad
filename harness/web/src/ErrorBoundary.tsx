/** Keeps a renderer failure local: React unmounts the whole tree when an effect throws, which
 *  turned a missing WebGL context into a blank app. Wrap anything that can fail hard in this. */

import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { label: string; children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.label}]`, error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="boundary-error" data-testid="boundary-error" role="alert">
        <b>{this.props.label} failed.</b>
        <span className="muted">{error.message || String(error)}</span>
        <button className="secondary" onClick={() => this.setState({ error: null })}>
          Try again
        </button>
      </div>
    );
  }
}
