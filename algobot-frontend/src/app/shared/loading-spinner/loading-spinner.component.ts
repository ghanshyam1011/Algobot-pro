import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-loading-spinner',
  standalone: true,
  template: `
    <div class="flex flex-col items-center justify-center gap-3 py-12">
      <div class="relative"
        [class.w-8]="size === 'sm'"
        [class.h-8]="size === 'sm'"
        [class.w-12]="size === 'md'"
        [class.h-12]="size === 'md'"
        [class.w-16]="size === 'lg'"
        [class.h-16]="size === 'lg'">
        <div class="absolute inset-0 rounded-full border-2 border-brand-200 dark:border-brand-900"></div>
        <div class="absolute inset-0 rounded-full border-2 border-transparent border-t-brand-600 animate-spin"></div>
      </div>
      <p *ngIf="message" class="text-sm text-slate-500 dark:text-slate-400">{{ message }}</p>
    </div>
  `,
  imports: [import('@angular/common').then(m => m.CommonModule)] as any
})
export class LoadingSpinnerComponent {
  @Input() size: 'sm' | 'md' | 'lg' = 'md';
  @Input() message = '';
}