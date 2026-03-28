import {
  Component, Input, OnChanges, OnDestroy, AfterViewInit,
  ElementRef, ViewChild
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Coin } from '../../../models/coin.model';

@Component({
  selector: 'app-macd-chart',
  standalone: true,
  imports: [CommonModule],
  template: `<div #chartContainer class="w-full" style="height:160px"></div>`
})
export class MacdChartComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() signals: any[] = [];
  @Input() coin!: Coin;

  @ViewChild('chartContainer') containerRef!: ElementRef<HTMLDivElement>;
  private chart: any;
  private histSeries: any;

  get isDark(): boolean { return document.documentElement.classList.contains('dark'); }

  async ngAfterViewInit(): Promise<void> { await this.initChart(); }
  async ngOnChanges(): Promise<void>     { if (this.chart) this.updateData(); }

  private async initChart(): Promise<void> {
    if (!this.containerRef?.nativeElement) return;
    try {
      const { createChart } = await import('lightweight-charts') as any;
      const dark = this.isDark;

      this.chart = createChart(this.containerRef.nativeElement, {
        width:  this.containerRef.nativeElement.clientWidth,
        height: 160,
        layout: { background: { color: 'transparent' }, textColor: dark ? '#94a3b8' : '#64748b', fontSize: 11 },
        grid: { vertLines: { color: 'transparent' }, horzLines: { color: dark ? '#1e2130' : '#f1f5f9' } },
        rightPriceScale: { borderColor: dark ? '#2a2d3e' : '#e2e8f0' },
        timeScale: { borderColor: dark ? '#2a2d3e' : '#e2e8f0', timeVisible: true },
      });

      this.histSeries = this.chart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
      this.updateData();

      const ro = new ResizeObserver(e => {
        const w = e[0]?.contentRect.width;
        if (w && this.chart) this.chart.applyOptions({ width: w });
      });
      ro.observe(this.containerRef.nativeElement);
    } catch (e) { console.warn('MACD chart error:', e); }
  }

  private updateData(): void {
    if (!this.histSeries || !this.signals?.length) return;
    const seen = new Set<number>();
    const data = this.signals
      .filter(s => s.macd_histogram != null && s.timestamp)
      .map(s => ({
        time:  Math.floor(new Date(s.timestamp).getTime() / 1000),
        value: Number(s.macd_histogram),
        color: Number(s.macd_histogram) >= 0 ? '#22c55e88' : '#ef444488',
      }))
      .filter(d => { if (seen.has(d.time)) return false; seen.add(d.time); return true; })
      .sort((a, b) => a.time - b.time);
    if (data.length) { this.histSeries.setData(data); this.chart?.timeScale().fitContent(); }
  }

  ngOnDestroy(): void { this.chart?.remove(); }
}