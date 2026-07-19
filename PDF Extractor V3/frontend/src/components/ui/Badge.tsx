type Variant = 'green' | 'amber' | 'accent' | 'muted'

const MAP: Record<Variant, string> = {
  green:  'bg-green/15 text-green',
  amber:  'bg-pending/15 text-pending',
  accent: 'bg-accent/15 text-accent',
  muted:  'bg-gray-100 dark:bg-white/10 text-gray-500 dark:text-gray-400',
}

export default function Badge({ label, variant = 'muted' }: { label: string; variant?: Variant }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${MAP[variant]}`}>
      {label}
    </span>
  )
}
