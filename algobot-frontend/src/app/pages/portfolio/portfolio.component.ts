import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { Signal } from '../../models/signal.model';
import { COINS, getCoin } from '../../models/coin.model';
import { SignalBadgeComponent } from '../../shared/signal-badge/signal-badge.component';

interface PaperTrade {
  coin:        string;
  direction:   'LONG' | 'SHORT';
  entryPrice:  number;
  exitPrice:   number;
  quantity:    number;
  posValue:    number;
  pnl:         number;
  pnlPct:      number;
  result:      'WIN' | 'LOSS';
  openedAt:    string;
  closedAt:    string;
  holdHours:   number;
}

@Component({
  selector: 'app-portfolio',
  standalone: true,
  imports: [CommonModule, FormsModule, SignalBadgeComponent],
  templateUrl: './portfolio.component.html',
  styleUrls: ['./portfolio.component.scss']
})
export class PortfolioComponent implements OnInit {
  api    = inject(ApiService);
  getCoin = getCoin;

  capital    = signal(50000);
  allSignals = signal<Signal[]>([]);
  trades     = signal<PaperTrade[]>([]);
  loading    = signal(true);

  // Computed stats
  totalTrades   = computed(() => this.trades().length);
  wins          = computed(() => this.trades().filter(t => t.result === 'WIN').length);
  losses        = computed(() => this.trades().filter(t => t.result === 'LOSS').length);
  winRate       = computed(() =>
    this.totalTrades() ? (this.wins() / this.totalTrades() * 100) : 0);
  totalPnl      = computed(() => this.trades().reduce((s, t) => s + t.pnl, 0));
  totalPnlPct   = computed(() => (this.totalPnl() / this.capital() * 100));
  avgWin        = computed(() => {
    const wins = this.trades().filter(t => t.pnl > 0);
    return wins.length ? wins.reduce((s, t) => s + t.pnl, 0) / wins.length : 0;
  });
  avgLoss       = computed(() => {
    const losses = this.trades().filter(t => t.pnl <= 0);
    return losses.length ? losses.reduce((s, t) => s + t.pnl, 0) / losses.length : 0;
  });

  // Signal distribution
  signalCounts = computed(() => {
    const sigs = this.allSignals();
    return {
      buy:  sigs.filter(s => s.signal === 'BUY').length,
      sell: sigs.filter(s => s.signal === 'SELL').length,
      hold: sigs.filter(s => s.signal === 'HOLD').length,
      total: sigs.length,
    };
  });

  // Equity curve data points
  equityCurve = computed(() => {
    let equity = this.capital();
    return [
      { trade: 0, value: equity },
      ...this.trades().map((t, i) => {
        equity += t.pnl;
        return { trade: i + 1, value: Math.round(equity) };
      })
    ];
  });

  ngOnInit(): void {
    const all: Signal[] = [];
    let done = 0;

    COINS.forEach(coin => {
      this.api.getHistory(coin.id, 500).subscribe({
        next: res => {
          all.push(...(res.signals ?? []));
          done++;
          if (done === COINS.length) {
            all.sort((a, b) =>
              new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
            );
            this.allSignals.set(all);
            this.trades.set(this.simulateTrades(all));
            this.loading.set(false);
          }
        },
        error: () => { done++; if (done === COINS.length) this.loading.set(false); }
      });
    });
  }

  private simulateTrades(signals: Signal[]): PaperTrade[] {
    const trades: PaperTrade[] = [];
    const FEE       = 0.001;
    const POS_PCT   = 0.10;
    const MAX_HOLD  = 48;
    const CONF_MIN  = 0.65;

    // Simulate per coin independently
    const byCoin: Record<string, Signal[]> = {};
    signals.forEach(s => {
      if (!byCoin[s.coin]) byCoin[s.coin] = [];
      byCoin[s.coin].push(s);
    });

    Object.values(byCoin).forEach(coinSigs => {
      let pos: { dir: string; price: number; qty: number; idx: number; ts: string } | null = null;
      const capital = this.capital();

      coinSigs.forEach((sig, i) => {
        if (!pos && sig.confidence >= CONF_MIN) {
          if (sig.signal === 'BUY') {
            const val = capital * POS_PCT;
            const qty = (val * (1 - FEE)) / sig.price;
            pos = { dir: 'LONG', price: sig.price, qty, idx: i, ts: sig.timestamp };
          }
        } else if (pos?.dir === 'LONG') {
          const held = i - pos.idx;
          if ((sig.signal === 'SELL' && sig.confidence >= CONF_MIN) || held >= MAX_HOLD) {
            const gross   = (sig.price - pos.price) * pos.qty;
            const fee     = sig.price * pos.qty * FEE;
            const pnl     = gross - fee;
            const posVal  = pos.price * pos.qty;
            trades.push({
              coin:       sig.coin,
              direction:  'LONG',
              entryPrice: pos.price,
              exitPrice:  sig.price,
              quantity:   pos.qty,
              posValue:   posVal,
              pnl:        Math.round(pnl * 100) / 100,
              pnlPct:     Math.round(pnl / posVal * 10000) / 100,
              result:     pnl > 0 ? 'WIN' : 'LOSS',
              openedAt:   pos.ts,
              closedAt:   sig.timestamp,
              holdHours:  held,
            });
            pos = null;
          }
        }
      });
    });

    return trades.sort((a, b) =>
      new Date(a.openedAt).getTime() - new Date(b.openedAt).getTime()
    );
  }

  pnlColor(v: number): string {
    return v >= 0
      ? 'text-green-600 dark:text-green-400'
      : 'text-red-600 dark:text-red-400';
  }

  formatPnl(v: number): string {
    return (v >= 0 ? '+' : '') + '₹' + Math.abs(v).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  }

  formatDate(ts: string): string {
    if (!ts) return '—';
    return new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric' });
  }

  // Equity chart bar height as % of max
  equityBarHeight(value: number): number {
    const curve = this.equityCurve();
    if (curve.length < 2) return 50;
    const values = curve.map(p => p.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    return Math.round(((value - min) / range) * 80 + 10);
  }
}