export default function EmptyState({ icon, title, description }: {
  icon?: string; title: string; description?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon && <div className="text-4xl mb-4 opacity-40">{icon}</div>}
      <p className="font-semibold text-gray-600 dark:text-gray-400">{title}</p>
      {description && <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">{description}</p>}
    </div>
  )
}
