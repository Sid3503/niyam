export function FilterSelect({ id, label, value, onChange, options, all = "All" }: { id: string; label: string; value: string; onChange: (v: string) => void; options: { value: string; label?: string }[]; all?: string }) {
  return (
    <div className="min-w-[8.5rem] flex-1 sm:flex-none">
      <label htmlFor={id} className="label mb-1 block">{label}</label>
      <select id={id} className="field !py-1.5 text-[12.5px]" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{all}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label ?? o.value}</option>)}
      </select>
    </div>
  );
}

export function uniq(values: (string | null | undefined)[]): { value: string }[] {
  return Array.from(new Set(values.filter((v): v is string => !!v))).sort().map((value) => ({ value }));
}
