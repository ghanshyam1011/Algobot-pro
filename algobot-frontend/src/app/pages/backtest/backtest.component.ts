import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../core/api.service';
import { BacktestResult } from '../../models/backtest.model';
import { COINS, Coin } from '../../models/coin.model';

export interface CoinBacktest {
  coin:    Coin;
  data:    BacktestResult | null;
  loading: boolean;
  error:   string;
}

export interface GateCheck {
  label:  string;
  value:  string;
  target: string;
  pass:   boolean;
}

@Component({
  selector: 'app-backtest',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './backtest.component.html',
  styleUrls: ['./backtest.component.scss']
})
export class BacktestComponent implements OnInit {
  Math  = Math;
  api   = inject(ApiService);
  coins = COINS;

  results      = signal<CoinBacktest[]>(
    COINS.map(c => ({ coin: c, data: null, loading: true, error: '' }))
  );
  selectedCoin = signal<string>('BTC_USD');

  selectedResult = computed(() =>
    this.results().find(r => r.coin.id === this.selectedCoin()) ?? null
  );

  thresholds = { win_rate: 52, total_return: 10, max_drawdown: -25, sharpe: 0.8, profit_factor: 1.2 };

  ngOnInit(): void {
    COINS.forEach((coin, i) => {
      this.api.getBacktest(coin.id).subscribe({
        next: data => this.results.update(prev => {
          const u = [...prev]; u[i] = { ...u[i], data, loading: false }; return u;
        }),
        error: err => this.results.update(prev => {
          const u = [...prev]; u[i] = { ...u[i], loading: false, error: err.message }; return u;
        })
      });
    });
  }

  passesGate(d: BacktestResult): boolean {
    return d.win_rate_pct     >= this.thresholds.win_rate      &&
           d.total_return_pct >= this.thresholds.total_return   &&
           d.max_drawdown_pct >= this.thresholds.max_drawdown   &&
           d.sharpe_ratio     >= this.thresholds.sharpe         &&
           d.profit_factor    >= this.thresholds.profit_factor;
  }

  getGateChecks(d: BacktestResult): GateCheck[] {
    return [
      { label: 'Win rate',     value: d.win_rate_pct.toFixed(1) + '%',       target: '>52%',  pass: d.win_rate_pct >= this.thresholds.win_rate },
      { label: 'Return',       value: this.formatReturn(d.total_return_pct),  target: '>10%',  pass: d.total_return_pct >= this.thresholds.total_return },
      { label: 'Drawdown',     value: d.max_drawdown_pct.toFixed(1) + '%',   target: '>-25%', pass: d.max_drawdown_pct >= this.thresholds.max_drawdown },
      { label: 'Sharpe',       value: d.sharpe_ratio.toFixed(2),             target: '>0.8',  pass: d.sharpe_ratio >= this.thresholds.sharpe },
      { label: 'Profit factor',value: d.profit_factor.toFixed(2),            target: '>1.2',  pass: d.profit_factor >= this.thresholds.profit_factor },
    ];
  }

  pnlColor(v: number): string {
    return v >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
  }

  metricColor(v: number, threshold: number): string {
    return v >= threshold ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
  }

  drawdownColor(v: number): string {
    return v >= this.thresholds.max_drawdown ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
  }

  formatReturn(v: number): string {
    return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  }

  capitalBarWidth(d: BacktestResult): number {
    return Math.min(100, Math.abs(d.total_return_pct) * 3 + 50);
  }
}