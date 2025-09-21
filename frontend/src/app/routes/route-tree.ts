import { homeRoute } from './home-route'
import { rootRoute } from './root-route'

export const routeTree = rootRoute.addChildren([homeRoute])
