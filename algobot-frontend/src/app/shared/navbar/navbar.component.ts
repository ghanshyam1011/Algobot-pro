import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ThemeService } from '../../core/theme.service';
import { SignalService } from '../../core/signal.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <header class="h-16 shrink-0 flex items-center gap-4 px-4 md:px-6
                   border-b border-light-border dark:border-dark-border
                   bg-light-surface dark:bg-dark-surface z-10">

      <button (click)="toggleSidebar.emit()"
        class="p-2 rounded-lg text-slate-500 hover:text-slate-700 dark:hover:text-white
               hover:bg-light-hover dark:hover:bg-dark-hover transition-colors">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
      </button>

      <div class="flex-1"></div>

      <span *ngIf="signalSvc.lastRefresh$ | async as lastRefresh"
        class="hidden md:block text-xs text-slate-400 dark:text-slate-500">
        Updated {{ formatTime(lastRefresh) }}
      </span>

      <button (click)="signalSvc.refresh()"
        [disabled]="(signalSvc.loading$ | async) === true"
        class="p-2 rounded-lg text-slate-500 hover:text-slate-700 dark:hover:text-white
               hover:bg-light-hover dark:hover:bg-dark-hover transition-colors disabled:opacity-40"
        title="Refresh signals">
        <svg class="w-5 h-5"
          [class.animate-spin]="(signalSvc.loading$ | async) === true"
          fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        </svg>
      </button>

      <button (click)="theme.toggle()"
        class="p-2 rounded-lg text-slate-500 hover:text-slate-700 dark:hover:text-white
               hover:bg-light-hover dark:hover:bg-dark-hover transition-colors"
        [title]="theme.isDark ? 'Switch to light' : 'Switch to dark'">
        <svg *ngIf="theme.isDark" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
        </svg>
        <svg *ngIf="!theme.isDark" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
        </svg>
      </button>

      <div class="flex items-center gap-1.5">
        <span class="w-2 h-2 rounded-full"
          [class.bg-green-500]="!(signalSvc.error$ | async)"
          [class.animate-pulse]="!(signalSvc.error$ | async)"
          [class.bg-red-500]="signalSvc.error$ | async">
        </span>
        <span class="hidden md:block text-xs text-slate-500 dark:text-slate-400">
          {{ (signalSvc.error$ | async) ? 'Offline' : 'Live' }}
        </span>
      </div>

    </header>
  `
})
export class NavbarComponent {
  @Input()  sidebarCollapsed = false;
  @Output() toggleSidebar    = new EventEmitter<void>();

  theme     = inject(ThemeService);
  signalSvc = inject(SignalService);

  formatTime(d: Date): string {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
}