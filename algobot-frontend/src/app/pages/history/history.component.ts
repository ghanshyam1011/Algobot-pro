import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { Signal, SignalType } from '../../models/signal.model';
import { COINS } from '../../models/coin.model';
import { SignalBadgeComponent } from '../../shared/signal-badge/signal-badge.component';
import { ConfidenceBarComponent } from '../../shared/confidence-bar/confidence-bar.component';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [CommonModule, FormsModule, SignalBadgeComponent, ConfidenceBarComponent],
  templateUrl: './history.component.html',
  styleUrls: ['./history.component.scss']
})
export class HistoryComponent implements OnInit {
  api    = inject(ApiService);
  coins  = COINS;

  allSignals  = signal<Signal[]>([]);
  loading     = signal(true);
  error       = signal('');

  filterCoin   = signal('');
  filterSignal = signal<SignalType | ''>('');
  filterMinConf = signal(0);
  searchText   = signal('');

  filtered = computed(() => {
    let data = this.allSignals();
    if (this.filterCoin())   data = data.filter(s => s.coin === this.filterCoin());
    if (this.filterSignal()) data = data.filter(s => s.signal === this.filterSignal());
    if (this.filterMinConf()) data = data.filter(s => s.confidence >= this.filterMinConf());
    return data.slice().reverse(); // newest first
  });

  get totalBuy()   { return this.allSignals().filter(s => s.signal === 'BUY').length; }
  get totalSell()  { return this.allSignals().filter(s => s.signal === 'SELL').length; }
  get totalHold()  { return this.allSignals().filter(s => s.signal === 'HOLD').length; }
  get avgConf()    {
    const s = this.allSignals();
    return s.length ? s.reduce((a, b) => a + b.confidence, 0) / s.length : 0;
  }

  ngOnInit(): void {
    // Load history for all coins and merge
    const all: Signal[] = [];
    let done = 0;

    this.coins.forEach(coin => {
      this.api.getHistory(coin.id, 200).subscribe({
        next: res => {
          all.push(...(res.signals ?? []));
          done++;
          if (done === this.coins.length) {
            all.sort((a, b) =>
              new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
            );
            this.allSignals.set(all);
            this.loading.set(false);
          }
        },
        error: () => { done++; if (done === this.coins.length) this.loading.set(false); }
      });
    });
  }

  formatDate(ts: string): string {
    if (!ts) return '—';
    return new Date(ts).toLocaleString([], {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  }

  exportCsv(): void {
    const rows = [
      ['Timestamp', 'Coin', 'Signal', 'Confidence', 'Price', 'Target', 'Stop Loss', 'RSI'],
      ...this.filtered().map(s => [
        s.timestamp, s.coin, s.signal,
        (s.confidence * 100).toFixed(1) + '%',
        s.price, s.target_price, s.stop_loss_price, s.rsi
      ])
    ];
    const csv  = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = 'algobot_signals.csv'; a.click();
    URL.revokeObjectURL(url);
  }
}