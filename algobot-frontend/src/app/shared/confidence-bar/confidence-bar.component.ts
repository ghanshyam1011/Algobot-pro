import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-confidence-bar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="flex items-center gap-2">
      <div class="flex-1 h-1.5 rounded-full bg-slate-200 dark:bg-dark-border overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-700"
          [ngClass]="barColor"
          [style.width.%]="confidence * 100">
        </div>
      </div>
      <span class="text-xs font-semibold font-mono w-10 text-right"
        [ngClass]="textColor">
        {{ (confidence * 100).toFixed(0) }}%
      </span>
    </div>
  `
})
export class ConfidenceBarComponent {
  @Input() confidence = 0;

  get barColor(): string {
    if (this.confidence >= 0.85) return 'bg-green-500';
    if (this.confidence >= 0.75) return 'bg-brand-500';
    if (this.confidence >= 0.65) return 'bg-amber-500';
    return 'bg-slate-400';
  }

  get textColor(): string {
    if (this.confidence >= 0.85) return 'text-green-600 dark:text-green-400';
    if (this.confidence >= 0.75) return 'text-brand-600 dark:text-brand-400';
    if (this.confidence >= 0.65) return 'text-amber-600 dark:text-amber-400';
    return 'text-slate-500 dark:text-slate-400';
  }
}