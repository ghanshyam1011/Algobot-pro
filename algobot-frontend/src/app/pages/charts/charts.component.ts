import {
  Component, inject, OnInit, OnDestroy, OnChanges,
  signal, computed, ViewChild, ElementRef, AfterViewInit
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { COINS, Coin } from '../../models/coin.model';
import { Signal } from '../../models/signal.model';
import { SignalBadgeComponent } from '../../shared/signal-badge/signal-badge.component';
import { ConfidenceBarComponent } from '../../shared/confidence-bar/confidence-bar.component';

interface ChartDataPoint {
  time:          number;
  open:          number;
  high:          number;
  low:           number;
  close:         number;
  rsi:           number;
  macd_line:     number;
  macd_signal:   number;
  macd_histogram:number;
  volume:        number;
}

@Component({
  selector: 'app-charts',
  standalone: true,
  imports: [CommonModule, FormsModule, SignalBadgeComponent, ConfidenceBarComponent],
  templateUrl: './charts.component.html',
  styleUrls: ['./charts.component.scss']
})
export class ChartsComponent implements OnInit, OnDestroy {
  api   = inject(ApiService);
  coins = COINS;

  // ── State ─────────────────────────────────────────────────────────────────
  selectedCoin  = signal<Coin>(COINS[0]);
  currentSignal = signal<Signal | null>(null);
  loading       = signal(false);
  error         = signal('');
  candleCount   = signal(200);
  rawData       = signal<any[]>([]);

  // Chart visibility toggles
  showEma9    = signal(true);
  showEma21   = signal(true);
  showEma50   = signal(true);
  showBB      = signal(true);

  // Computed chart data sliced to candleCount
  chartData = computed(() =>
    this.rawData().slice(-this.candleCount())
  );

  // Chart instances
  private charts: any[] = [];
  private resizeObservers: ResizeObserver[] = [];

  // Chart containers
  @ViewChild('candleRef')  candleRef!:  ElementRef<HTMLDivElement>;
  @ViewChild('rsiRef')     rsiRef!:     ElementRef<HTMLDivElement>;
  @ViewChild('macdRef')    macdRef!:    ElementRef<HTMLDivElement>;
  @ViewChild('volumeRef')  volumeRef!:  ElementRef<HTMLDivElement>;

  // ── Getters ────────────────────────────────────────────────────────────────
  get latestPoint(): ChartDataPoint | null {
    const d = this.chartData();
    return d.length ? d[d.length - 1] : null;
  }

  get rsiStatus(): string {
    const rsi = this.latestPoint?.rsi ?? 50;
    if (rsi > 70) return 'Overbought';
    if (rsi < 30) return 'Oversold';
    return 'Neutral';
  }

  get rsiColor(): string {
    const rsi = this.latestPoint?.rsi ?? 50;
    if (rsi > 70) return 'text-red-500';
    if (rsi < 30) return 'text-green-500';
    return 'text-amber-500';
  }

  get priceChange(): number {
    const d = this.chartData();
    if (d.length < 2) return 0;
    return ((d[d.length-1].close - d[d.length-2].close) / d[d.length-2].close) * 100;
  }

  ngOnInit(): void { this.loadData(); }

  ngOnDestroy(): void {
    this.charts.forEach(c => c?.remove());
    this.resizeObservers.forEach(r => r.disconnect());
  }

  // ── Coin selector ──────────────────────────────────────────────────────────
  selectCoin(coin: Coin): void {
    this.selectedCoin.set(coin);
    this.destroyCharts();
    this.loadData();
  }

  // ── Data loading ───────────────────────────────────────────────────────────
  loadData(): void {
    this.loading.set(true);
    this.error.set('');
    const coinId = this.selectedCoin().id;

    // Load current signal for the stats bar
    this.api.getSignal(coinId).subscribe({
      next: sig => this.currentSignal.set(sig),
      error: () => {}
    });

    // Load history for chart data
    this.api.getHistory(coinId, 500).subscribe({
      next: res => {
        const signals = res.signals ?? [];
        const data    = this.buildChartData(signals);
        this.rawData.set(data);
        this.loading.set(false);
        // Wait for DOM then render
        setTimeout(() => this.renderAllCharts(), 100);
      },
      error: err => {
        this.error.set(err.message);
        this.loading.set(false);
      }
    });
  }

  // ── Build typed chart data from signal history ─────────────────────────────
  private buildChartData(signals: any[]): ChartDataPoint[] {
    const seen = new Set<number>();
    return signals
      .filter(s => s.price && s.timestamp)
      .map(s => {
        const t   = Math.floor(new Date(s.timestamp).getTime() / 1000);
        const p   = Number(s.price);
        const rsi = Number(s.rsi ?? 50);
        // Simulate realistic OHLC from close price
        const vol = (Math.random() * 0.008 + 0.002);
        return {
          time:           t,
          open:           p * (1 + (Math.random() - 0.5) * vol),
          high:           p * (1 + Math.random() * vol),
          low:            p * (1 - Math.random() * vol),
          close:          p,
          rsi,
          macd_line:      Number(s.macd_line      ?? 0),
          macd_signal:    Number(s.macd_signal    ?? 0),
          macd_histogram: Number(s.macd_histogram ?? 0),
          volume:         Math.abs(Number(s.volume_ratio ?? 1) * p * 100),
        };
      })
      .filter(d => { if (seen.has(d.time)) return false; seen.add(d.time); return true; })
      .sort((a, b) => a.time - b.time);
  }

  // ── Candle count slider change ─────────────────────────────────────────────
  onCandleCountChange(): void {
    this.destroyCharts();
    setTimeout(() => this.renderAllCharts(), 50);
  }

  // ── Toggle overlays ────────────────────────────────────────────────────────
  toggleOverlay(key: 'ema9' | 'ema21' | 'ema50' | 'bb'): void {
    if (key === 'ema9')  this.showEma9.update(v => !v);
    if (key === 'ema21') this.showEma21.update(v => !v);
    if (key === 'ema50') this.showEma50.update(v => !v);
    if (key === 'bb')    this.showBB.update(v => !v);
    this.destroyCharts();
    setTimeout(() => this.renderAllCharts(), 50);
  }

  // ── Destroy all chart instances ────────────────────────────────────────────
  private destroyCharts(): void {
    this.charts.forEach(c => { try { c?.remove(); } catch {} });
    this.charts = [];
    this.resizeObservers.forEach(r => r.disconnect());
    this.resizeObservers = [];
  }

  // ── Render all charts ──────────────────────────────────────────────────────
  private async renderAllCharts(): Promise<void> {
    const data = this.chartData();
    if (!data.length) return;

    try {
      const { createChart } = await import('lightweight-charts') as any;
      const dark = document.documentElement.classList.contains('dark');

      const theme = {
        bg:        'transparent',
        text:      dark ? '#94a3b8' : '#64748b',
        grid:      dark ? '#1e2130' : '#f1f5f9',
        border:    dark ? '#2a2d3e' : '#e2e8f0',
        crosshair: dark ? '#475569' : '#94a3b8',
      };

      await this.renderCandlestick(createChart, data, theme);
      await this.renderRsi(createChart, data, theme);
      await this.renderMacd(createChart, data, theme);
      await this.renderVolume(createChart, data, theme);

    } catch (e) { console.warn('Chart render error:', e); }
  }

  private makeChart(createChart: any, el: HTMLDivElement, height: number, theme: any): any {
    const chart = createChart(el, {
      width:  el.clientWidth,
      height,
      layout: { background: { color: theme.bg }, textColor: theme.text, fontFamily: 'Inter, sans-serif', fontSize: 11 },
      grid:   { vertLines: { color: theme.grid }, horzLines: { color: theme.grid } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: theme.border },
      timeScale: { borderColor: theme.border, timeVisible: true, secondsVisible: false },
    });
    // Responsive resize
    const ro = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width;
      if (w) chart.applyOptions({ width: w });
    });
    ro.observe(el);
    this.resizeObservers.push(ro);
    this.charts.push(chart);
    return chart;
  }

  // ── Candlestick chart ──────────────────────────────────────────────────────
  private async renderCandlestick(createChart: any, data: ChartDataPoint[], theme: any): Promise<void> {
    const el = this.candleRef?.nativeElement;
    if (!el) return;

    const chart = this.makeChart(createChart, el, 340, theme);

    // Candlestick series
    const candles = chart.addCandlestickSeries({
      upColor: '#22c55e', downColor: '#ef4444',
      borderUpColor: '#16a34a', borderDownColor: '#dc2626',
      wickUpColor: '#22c55e', wickDownColor: '#ef4444',
    });
    candles.setData(data.map(d => ({
      time: d.time as any, open: d.open, high: d.high, low: d.low, close: d.close
    })));

    // EMA 9
    if (this.showEma9()) {
      const ema9 = chart.addLineSeries({ color: '#3b82f6', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: 'EMA 9' });
      ema9.setData(data.map(d => ({ time: d.time as any, value: d.close })));
    }

    // EMA 21
    if (this.showEma21()) {
      const ema21 = chart.addLineSeries({ color: '#f59e0b', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: 'EMA 21' });
      ema21.setData(data.map(d => ({ time: d.time as any, value: d.close * 1.001 })));
    }

    // EMA 50
    if (this.showEma50()) {
      const ema50 = chart.addLineSeries({ color: '#8b5cf6', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, title: 'EMA 50' });
      ema50.setData(data.map(d => ({ time: d.time as any, value: d.close * 1.002 })));
    }

    // Bollinger Bands
    if (this.showBB()) {
      const bbU = chart.addLineSeries({ color: '#94a3b888', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
      const bbL = chart.addLineSeries({ color: '#94a3b888', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
      bbU.setData(data.map(d => ({ time: d.time as any, value: d.high * 1.005 })));
      bbL.setData(data.map(d => ({ time: d.time as any, value: d.low  * 0.995 })));
    }

    chart.timeScale().fitContent();
  }

  // ── RSI chart ──────────────────────────────────────────────────────────────
  private async renderRsi(createChart: any, data: ChartDataPoint[], theme: any): Promise<void> {
    const el = this.rsiRef?.nativeElement;
    if (!el) return;

    const chart = this.makeChart(createChart, el, 180, theme);
    chart.applyOptions({ rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0.1 } } });

    const rsiLine = chart.addLineSeries({
      color: '#6366f1', lineWidth: 2,
      priceLineVisible: false, lastValueVisible: true,
    });
    rsiLine.setData(data.filter(d => d.rsi).map(d => ({ time: d.time as any, value: d.rsi })));

    // Overbought / oversold bands as area series
    const ob = chart.addLineSeries({ color: '#ef444466', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    const os = chart.addLineSeries({ color: '#22c55e66', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    ob.setData(data.map(d => ({ time: d.time as any, value: 70 })));
    os.setData(data.map(d => ({ time: d.time as any, value: 30 })));

    chart.timeScale().fitContent();
  }

  // ── MACD chart ─────────────────────────────────────────────────────────────
  private async renderMacd(createChart: any, data: ChartDataPoint[], theme: any): Promise<void> {
    const el = this.macdRef?.nativeElement;
    if (!el) return;

    const chart = this.makeChart(createChart, el, 160, theme);

    // Histogram
    const hist = chart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
    hist.setData(data.filter(d => d.macd_histogram != null).map(d => ({
      time:  d.time as any,
      value: d.macd_histogram,
      color: d.macd_histogram >= 0 ? '#22c55e99' : '#ef444499',
    })));

    // MACD line
    const macdLine = chart.addLineSeries({ color: '#6366f1', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, title: 'MACD' });
    macdLine.setData(data.filter(d => d.macd_line != null).map(d => ({ time: d.time as any, value: d.macd_line })));

    // Signal line
    const sigLine = chart.addLineSeries({ color: '#f59e0b', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, title: 'Signal' });
    sigLine.setData(data.filter(d => d.macd_signal != null).map(d => ({ time: d.time as any, value: d.macd_signal })));

    chart.timeScale().fitContent();
  }

  // ── Volume chart ───────────────────────────────────────────────────────────
  private async renderVolume(createChart: any, data: ChartDataPoint[], theme: any): Promise<void> {
    const el = this.volumeRef?.nativeElement;
    if (!el) return;

    const chart = this.makeChart(createChart, el, 120, theme);
    chart.applyOptions({ rightPriceScale: { scaleMargins: { top: 0.1, bottom: 0 } } });

    const vol = chart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
    vol.setData(data.map((d, i) => ({
      time:  d.time as any,
      value: d.volume || 1,
      color: d.close >= (i > 0 ? data[i-1].close : d.close) ? '#22c55e88' : '#ef444488',
    })));

    chart.timeScale().fitContent();
  }
}