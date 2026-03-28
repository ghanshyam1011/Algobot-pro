import { Component, Input, Output, EventEmitter } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';

interface NavItem {
  path:  string;
  label: string;
  icon:  string;
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, CommonModule],
  template: `
    <aside
      class="flex flex-col shrink-0 h-full border-r border-light-border dark:border-dark-border
             bg-light-surface dark:bg-dark-surface transition-all duration-300 z-20"
      [class.w-60]="!collapsed"
      [class.w-16]="collapsed">

      <!-- Logo -->
      <div class="flex items-center gap-3 h-16 px-4 border-b border-light-border dark:border-dark-border shrink-0">
        <div class="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center shrink-0">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
          </svg>
        </div>
        <span *ngIf="!collapsed"
          class="font-bold text-base text-slate-900 dark:text-white whitespace-nowrap">
          AlgoBot Pro
        </span>
      </div>

      <!-- Nav items -->
      <nav class="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        <a *ngFor="let item of navItems"
          [routerLink]="item.path"
          routerLinkActive="active"
          class="nav-link group"
          [title]="collapsed ? item.label : ''">

          <span class="shrink-0 w-5 h-5" [innerHTML]="item.icon"></span>

          <span *ngIf="!collapsed"
            class="truncate">{{ item.label }}</span>
        </a>
      </nav>

      <!-- Collapse toggle -->
      <div class="px-2 py-3 border-t border-light-border dark:border-dark-border shrink-0">
        <button
          (click)="toggleCollapse.emit()"
          class="w-full flex items-center justify-center p-2 rounded-lg
                 text-slate-400 hover:text-slate-700 dark:hover:text-white
                 hover:bg-light-hover dark:hover:bg-dark-hover transition-colors">
          <svg class="w-5 h-5 transition-transform duration-300"
            [class.rotate-180]="collapsed"
            fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M11 19l-7-7 7-7m8 14l-7-7 7-7"/>
          </svg>
        </button>
      </div>

    </aside>
  `
})
export class SidebarComponent {
  @Input()  collapsed = false;
  @Output() toggleCollapse = new EventEmitter<void>();

  navItems: NavItem[] = [
    {
      path: '/dashboard',
      label: 'Live Signals',
      icon: `<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                 d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
             </svg>`
    },
    {
      path: '/charts',
      label: 'Charts',
      icon: `<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                 d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/>
             </svg>`
    },
    {
      path: '/history',
      label: 'History',
      icon: `<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                 d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
             </svg>`
    },
    {
      path: '/backtest',
      label: 'Backtest',
      icon: `<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                 d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/>
             </svg>`
    },
    {
      path: '/portfolio',
      label: 'Portfolio',
      icon: `<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                 d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
             </svg>`
    },
  ];
}