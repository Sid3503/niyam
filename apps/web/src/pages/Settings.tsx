import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check as CheckIcon } from "lucide-react";
import { HereStrip, PageHeader, Field } from "@/components/Page";
import { currentActor, currentApiKey, DEFAULT_ACTOR, setActor, setApiKey } from "@/lib/settings";
import { useTour } from "@/components/Tour";

export default function SettingsPage() {
  const qc = useQueryClient();
  const tour = useTour();
  const [key, setKey] = React.useState(currentApiKey());
  const [actor, setActorValue] = React.useState(currentActor());
  const [saved, setSaved] = React.useState(false);

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    setApiKey(key.trim());
    setActor(actor.trim());
    void qc.invalidateQueries();
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2500);
  };

  return (
    <>
      <PageHeader eyebrow="Settings" title="Your name on every yes" lede="When you approve a fix, this name is what sales sees on the deck and what the proof pack records. Paste the demo API key here if you have not unlocked the pack yet." />
      <HereStrip here="A fix without a name is not clear to send." next="Next: save, then open Approvals and sign the top item." />
      <form onSubmit={save} className="sheet max-w-[560px] p-5">
        <Field label="API key" htmlFor="api-key">
          <input id="api-key" className="field font-mono" type="password" autoComplete="off" spellCheck={false} value={key} onChange={(e) => setKey(e.target.value)} placeholder="Leave empty when the API is open" />
        </Field>
        <Field label="Your name" htmlFor="actor" className="mt-4">
          <input id="actor" className="field" autoComplete="off" value={actor} onChange={(e) => setActorValue(e.target.value)} placeholder={DEFAULT_ACTOR} />
        </Field>
        <p className="mt-2 text-[12px] text-[var(--muted-foreground)]">
          Both are kept in this browser only and sent only to this workspace's server. Leave the name empty to act as {DEFAULT_ACTOR}.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button type="submit" className="btn btn-primary">Save</button>
          {saved ? <span role="status" className="flex items-center gap-1 text-[12px] text-[var(--ok-ink)]"><CheckIcon size={14} /> Saved</span> : null}
          <button type="button" className="btn" onClick={tour.start}>Start the 2-minute walkthrough</button>
        </div>
      </form>
    </>
  );
}
