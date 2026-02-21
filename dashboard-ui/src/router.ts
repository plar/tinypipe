import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'fleet-command',
    component: () => import('./views/PipelineListView.vue'),
    meta: { title: 'Fleet Command' },
  },
  {
    path: '/pipeline/:hash',
    name: 'pipeline-detail',
    component: () => import('./views/PipelineDetailView.vue'),
    meta: { title: 'Pipeline' },
  },
  {
    path: '/run/:id',
    name: 'run-detail',
    component: () => import('./views/RunDetailView.vue'),
    meta: { title: 'Run' },
  },
  {
    path: '/compare',
    name: 'compare',
    component: () => import('./views/CompareView.vue'),
    meta: { title: 'Compare' },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
