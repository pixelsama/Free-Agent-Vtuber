import { createRouter } from '@tanstack/react-router'

import { queryClient } from '@/app/query-client'
import { routeTree } from '@/app/routes/route-tree'

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  context: {
    queryClient,
  },
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
