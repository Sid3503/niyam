import * as React from "react";
import { api } from "@/lib/api";

/** Fetch a protected file with auth headers and expose it as an object URL (<audio>/<img> cannot send X-API-Key). */
export function useBlobUrl(url: string | null | undefined): { src: string | null; loading: boolean; error: unknown } {
  const [state, setState] = React.useState<{ src: string | null; loading: boolean; error: unknown }>({ src: null, loading: !!url, error: null });
  React.useEffect(() => {
    if (!url) { setState({ src: null, loading: false, error: null }); return; }
    let live = true;
    let made: string | null = null;
    setState({ src: null, loading: true, error: null });
    api.blob(url).then(
      (b) => { if (!live) return; made = URL.createObjectURL(b); setState({ src: made, loading: false, error: null }); },
      (e: unknown) => { if (live) setState({ src: null, loading: false, error: e }); },
    );
    return () => { live = false; if (made) URL.revokeObjectURL(made); };
  }, [url]);
  return state;
}

export function downloadBlob(filename: string, blob: Blob): void {
  const u = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = u;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(u);
}
