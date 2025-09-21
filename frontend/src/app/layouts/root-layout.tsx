import type { ReactNode } from 'react'

interface RootLayoutProps {
  readonly children: ReactNode
}

/**
 * RootLayout provides the full-bleed app background while the page components define layout.
 */
export function RootLayout({ children }: RootLayoutProps) {
  return (
    <div className="min-h-screen bg-[#F3EDF7] text-foreground">
      {children}
    </div>
  )
}
