import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SignalService } from '../../core/signal.service';
import { Signal } from '../../models/signal.model';
import { COINS, Coin, getCoin } from '../../models/coin.model';
import { SignalCardComponent } from './signal-card/signal-card.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, SignalCardComponent],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent {
  signalSvc = inject(SignalService);
  coins     = COINS;

  getCoin = getCoin;

  getSignal(signals: Record<string, Signal>, coinId: string): Signal | null {
    return signals[coinId] ?? null;
  }

  get summaryStats() {
    const sigs = Object.values(this.signalSvc['_signals'].value);
    return {
      buy:  sigs.filter(s => s.signal === 'BUY').length,
      sell: sigs.filter(s => s.signal === 'SELL').length,
      hold: sigs.filter(s => s.signal === 'HOLD').length,
      avgConf: sigs.length
        ? sigs.reduce((acc, s) => acc + s.confidence, 0) / sigs.length
        : 0,
    };
  }
}