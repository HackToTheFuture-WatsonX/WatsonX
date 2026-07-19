import { CheckCircle2, Info, AlertTriangle, XCircle, X } from 'lucide-react'
import { useToastStore, type ToastKind } from '../../store/toast'

const ICONS: Record<ToastKind, React.ReactNode> = {
  info:    <Info size={16} />,
  success: <CheckCircle2 size={16} />,
  warning: <AlertTriangle size={16} />,
  error:   <XCircle size={16} />,
}

const STYLES: Record<ToastKind, string> = {
  info:    'border-l-accent text-accent',
  success: 'border-l-green text-green-600 dark:text-green-400',
  warning: 'border-l-amber-400 text-amber-600 dark:text-amber-400',
  error:   'border-l-red-400 text-red-500',
}

export default function ToastHost() {
  const { toasts, dismiss } = useToastStore()

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-start gap-2.5 rounded-lg border-l-4 shadow-lg px-3.5 py-3
                      bg-card-light dark:bg-card-dark
                      border border-border-light dark:border-border-dark ${STYLES[t.kind]}`}
        >
          <span className="shrink-0 mt-0.5">{ICONS[t.kind]}</span>
          <p className="flex-1 text-sm text-gray-700 dark:text-gray-200 leading-snug">{t.message}</p>
          <button
            onClick={() => dismiss(t.id)}
            className="shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
            title="Dismiss"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
