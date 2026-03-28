import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Signal } from '../../../models/signal.model';
import { Coin } from '../../../models/coin.model';
import { SignalBadgeComponent } from '../../../shared/signal-badge/signal-badge.component';
import { ConfidenceBarComponent } from '../../../shared/confidence-bar/confidence-bar.component';

@Component({
  selector: 'app-signal-card',
  standalone: true,
  imports: [CommonModule, SignalBadgeComponent, ConfidenceBarComponent],
  templateUrl: './signal-card.component.html',
  styleUrls: ['./signal-card.component.scss']
})
export class SignalCardComponent {
  @Input() signal!: Signal;
  @Input() coin!: Coin;

  expanded = false;

  get borderColor(): string {
    return {
      BUY:  'border-green-400 dark:border-green-600',
      SELL: 'border-red-400 dark:border-red-600',
      HOLD: 'border-amber-400 dark:border-amber-600',
    }[this.signal.signal] ?? 'border-slate-300 dark:border-dark-border';
  }

  get accentBg(): string {
    return {
      BUY:  'bg-green-50 dark:bg-green-900/10',
      SELL: 'bg-red-50 dark:bg-red-900/10',
      HOLD: 'bg-amber-50 dark:bg-amber-900/10',
    }[this.signal.signal] ?? '';
  }

  get targetPct(): string {
    const pct = (this.signal.target_price - this.signal.price) / this.signal.price * 100;
    return (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%';
  }

  get stopPct(): string {
    const pct = (this.signal.stop_loss_price - this.signal.price) / this.signal.price * 100;
    return (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%';
  }

  get timeAgo(): string {
    if (!this.signal.timestamp) return '';
    const diff = Date.now() - new Date(this.signal.timestamp).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    return `${Math.floor(mins / 60)}h ago`;
  }
}