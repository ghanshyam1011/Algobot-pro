import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SignalType } from '../../models/signal.model';

@Component({
  selector: 'app-signal-badge',
  standalone: true,
  imports: [CommonModule],
  template: `
    <span [ngClass]="badgeClass" class="font-mono">
      <span class="w-1.5 h-1.5 rounded-full inline-block" [ngClass]="dotClass"></span>
      {{ signal }}
    </span>
  `
})
export class SignalBadgeComponent {
  @Input() signal: SignalType = 'HOLD';
  @Input() size: 'sm' | 'md' | 'lg' = 'md';

  get badgeClass(): string {
    const base = 'inline-flex items-center gap-1.5 rounded-full font-semibold ';
    const sizes = { sm: 'px-2 py-0.5 text-xs', md: 'px-2.5 py-0.5 text-xs', lg: 'px-3 py-1 text-sm' };
    const colors = {
      BUY:  'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-400',
      SELL: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-400',
      HOLD: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-400',
    };
    return base + sizes[this.size] + ' ' + (colors[this.signal] ?? colors.HOLD);
  }

  get dotClass(): string {
    return {
      BUY:  'bg-green-500',
      SELL: 'bg-red-500',
      HOLD: 'bg-amber-500',
    }[this.signal] ?? 'bg-amber-500';
  }
}