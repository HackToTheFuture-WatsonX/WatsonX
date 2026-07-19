import { type ReactNode } from 'react'

interface Props {
  children:  ReactNode
  className?: string
  padding?:   string
}

export default function Card({ children, className = '', padding = 'p-5' }: Props) {
  return (
    <div className={`card ${padding} ${className}`}>
      {children}
    </div>
  )
}
