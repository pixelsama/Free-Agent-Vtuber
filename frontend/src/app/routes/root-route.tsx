import { Outlet, createRootRoute } from '@tanstack/react-router'

import { RootLayout } from '@/app/layouts/root-layout'

export const rootRoute = createRootRoute({
  component: () => (
    <RootLayout>
      <Outlet />
    </RootLayout>
  ),
})
