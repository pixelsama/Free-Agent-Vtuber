import type { ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'

import { TooltipProvider } from '@/components/ui/tooltip'

import { queryClient } from '@/app/query-client'

interface AppProvidersProps {
  readonly children: ReactNode
}

export function AppProviders({ children }: AppProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={150}>
        {children}
        {import.meta.env.DEV ? <ReactQueryDevtools initialIsOpen={false} /> : null}
      </TooltipProvider>
    </QueryClientProvider>
  )
}
