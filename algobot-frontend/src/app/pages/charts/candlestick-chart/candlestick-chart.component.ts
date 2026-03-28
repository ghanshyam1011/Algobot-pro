import {
  Component, Input, OnChanges, OnDestroy, AfterViewInit,
  ElementRef, ViewChild
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Coin } from '../../../models/coin.model';
import { Signal } from '../../../models/signal.model';

@Component({
  selector: 'app-candlestick-chart',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div #chartContainer class="w-full" style="height:340px"></div>
    <p *ngIf="!signals?.length"
      class="flex items-center justify-center h-64 text-sm text-slate-400 dark:text-slate-500">
      No chart data yet — signals accumulate over time.
    </p>
  `
})
export class CandlestickChartComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() signals:       any[]         = [];
  @Input() coin!:         Coin;
  @Input() currentSignal: Signal | null = null;

  @ViewChild('chartContainer') containerRef!: ElementRef<HTMLDivElement>;

  private chart: any;
  private candleSeries: any;

  get isDark(): boolean {
    return document.documentElement.classList.contains('dark');
  }

  async ngAfterViewInit(): Promise<void> { await this.initChart(); }
  async ngOnChanges(): Promise<void>     { if (this.chart) this.updateData(); }

  private async initChart(): Promise<void> {
    if (!this.containerRef?.nativeElement) return;
    try {
      const { createChart } = await import('lightweight-charts') as any;
      const dark = this.isDark;

      this.chart = createChart(this.containerRef.nativeElement, {
        width:  this.containerRef.nativeElement.clientWidth,
        height: 340,
        layout: {
          background: { color: 'transparent' },
          textColor:  dark ? '#94a3b8' : '#64748b',
          fontFamily: 'Inter, system-ui, sans-serif',
          fontSize:   12,
        },
        grid: {
          vertLines: { color: dark ? '#1e2130' : '#f1f5f9' },
          horzLines: { color: dark ? '#1e2130' : '#f1f5f9' },
        },
        crosshair: { mode: 1 },
        rightPriceScale: { borderColor: dark ? '#2a2d3e' : '#e2e8f0' },
        timeScale: { borderColor: dark ? '#2a2d3e' : '#e2e8f0', timeVisible: true, secondsVisible: false },
      });

      this.candleSeries = this.chart.addCandlestickSeries({
        upColor: '#22c55e', downColor: '#ef4444',
        borderUpColor: '#16a34a', borderDownColor: '#dc2626',
        wickUpColor: '#22c55e', wickDownColor: '#ef4444',
      });

      this.updateData();

      const ro = new ResizeObserver(entries => {
        const w = entries[0]?.contentRect.width;
        if (w && this.chart) this.chart.applyOptions({ width: w });
      });
      ro.observe(this.containerRef.nativeElement);
    } catch (e) { console.warn('Chart init failed:', e); }
  }

  private updateData(): void {
    if (!this.candleSeries || !this.signals?.length) return;
    const seen = new Set<number>();
    const candles = this.signals
      .filter(s => s.price && s.timestamp)
      .map(s => {
        const t = Math.floor(new Date(s.timestamp).getTime() / 1000);
        const p = Number(s.price);
        return { time: t, open: p * 0.998, high: p * 1.005, low: p * 0.995, close: p };
      })
      .filter(c => { if (seen.has(c.time)) return false; seen.add(c.time); return true; })
      .sort((a, b) => a.time - b.time);

    if (candles.length) {
      this.candleSeries.setData(candles);
      this.chart?.timeScale().fitContent();
    }
  }

  ngOnDestroy(): void { this.chart?.remove(); }
}