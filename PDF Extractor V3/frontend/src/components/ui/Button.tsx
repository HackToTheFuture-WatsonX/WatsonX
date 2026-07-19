import { type ButtonHTMLAttributes } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'teal' | 'green' | 'danger'
  size?:    'sm' | 'md'
}

const VARIANTS = {
  primary: 'bg-accent hover:bg-accent-dark text-white',
  ghost:   'bg-transparent hover:bg-gray-100 dark:hover:bg-white/10 text-gray-600 dark:text-gray-400',
  teal:    'bg-teal hover:bg-teal/80 text-white',
  green:   'bg-green hover:bg-green/80 text-white',
  danger:  'bg-red-500 hover:bg-red-600 text-white',
}

const SIZES = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
}

export default function Button({ variant = 'primary', size = 'md', className = '', children, ...rest }: Props) {
  return (
    <button
      className={`
        ${VARIANTS[variant]} ${SIZES[size]}
        font-semibold rounded-lg transition-colors duration-150
        disabled:opacity-40 disabled:cursor-not-allowed
        flex items-center gap-1.5 ${className}
      `}
      {...rest}
    >
      {children}
    </button>
  )
}
