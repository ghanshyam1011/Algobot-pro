import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  {
    path: 'dashboard',
    loadComponent: () =>
      import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent),
    title: 'Live Signals — AlgoBot Pro'
  },
  {
    path: 'charts',
    loadComponent: () =>
      import('./pages/charts/charts.component').then(m => m.ChartsComponent),
    title: 'Charts — AlgoBot Pro'
  },
  {
    path: 'history',
    loadComponent: () =>
      import('./pages/history/history.component').then(m => m.HistoryComponent),
    title: 'Signal History — AlgoBot Pro'
  },
  {
    path: 'backtest',
    loadComponent: () =>
      import('./pages/backtest/backtest.component').then(m => m.BacktestComponent),
    title: 'Backtest — AlgoBot Pro'
  },
  {
    path: 'portfolio',
    loadComponent: () =>
      import('./pages/portfolio/portfolio.component').then(m => m.PortfolioComponent),
    title: 'Portfolio — AlgoBot Pro'
  },
  { path: '**', redirectTo: 'dashboard' }
];