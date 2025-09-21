import type { ReactNode } from 'react'

interface RootLayoutProps {
  readonly children: ReactNode
}

/**
 * RootLayout centers the prototype canvas and applies the Material-inspired background.
 */
export function RootLayout({ children }: RootLayoutProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F3EDF7] text-foreground">
      <div className="w-full max-w-[930px] px-4 py-10 sm:px-8">
        <div className="rounded-[18px] border-[8px] border-[#CAC4D0] bg-[#FEF7FF] shadow-[0px_12px_40px_rgba(98,91,113,0.12)]">
          {children}
        </div>
      </div>
    </div>
  )
}
