import { RouterProvider } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/router-devtools'

import { AppProviders } from '@/app/providers/app-providers'
import { router } from '@/app/router'

function App() {
  return (
    <AppProviders>
      <RouterProvider router={router} />
      {import.meta.env.DEV ? (
        <TanStackRouterDevtools router={router} position="bottom-right" />
      ) : null}
    </AppProviders>
  )
}

export default App
