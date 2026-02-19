import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'pipelines',
    component: () => import('./views/PipelineListView.vue'),
  },
  {
    path: '/pipeline/:hash',
    name: 'pipeline-detail',
    component: () => import('./views/PipelineDetailView.vue'),
  },
  {
    path: '/run/:id',
    name: 'run-detail',
    component: () => import('./views/RunDetailView.vue'),
  },
  {
    path: '/compare',
    name: 'compare',
    component: () => import('./views/CompareView.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
