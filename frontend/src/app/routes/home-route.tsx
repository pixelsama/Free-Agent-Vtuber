import { createRoute } from '@tanstack/react-router'

import { ChatHomePage } from '@/features/chat/pages/chat-home'

import { rootRoute } from './root-route'

export const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: ChatHomePage,
})
