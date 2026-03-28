import { Injectable, inject, OnDestroy } from '@angular/core';
import { BehaviorSubject, interval, Subscription, switchMap, startWith, catchError, of } from 'rxjs';
import { ApiService } from './api.service';
import { Signal } from '../models/signal.model';
import { environment } from '../../environments/environment';

@Injectable({ providedIn: 'root' })
export class SignalService implements OnDestroy {
  private api = inject(ApiService);

  // Live signal store — all components subscribe to this
  private _signals = new BehaviorSubject<Record<string, Signal>>({});
  private _loading = new BehaviorSubject<boolean>(true);
  private _error   = new BehaviorSubject<string | null>(null);
  private _lastRefresh = new BehaviorSubject<Date | null>(null);

  signals$     = this._signals.asObservable();
  loading$     = this._loading.asObservable();
  error$       = this._error.asObservable();
  lastRefresh$ = this._lastRefresh.asObservable();

  private pollSub?: Subscription;

  constructor() {
    this.startPolling();
  }

  startPolling(): void {
    this.pollSub?.unsubscribe();

    // Poll immediately, then every refreshIntervalMs
    this.pollSub = interval(environment.refreshIntervalMs).pipe(
      startWith(0),
      switchMap(() => {
        this._loading.next(true);
        return this.api.getAllSignals().pipe(
          catchError(err => {
            this._error.next(err.message);
            this._loading.next(false);
            return of({ signals: {}, count: 0, timestamp: '' });
          })
        );
      })
    ).subscribe(response => {
      if (response.signals) {
        this._signals.next(response.signals);
        this._error.next(null);
        this._lastRefresh.next(new Date());
      }
      this._loading.next(false);
    });
  }

  refresh(): void {
    this._loading.next(true);
    this.api.getAllSignals().pipe(
      catchError(err => {
        this._error.next(err.message);
        this._loading.next(false);
        return of({ signals: {}, count: 0, timestamp: '' });
      })
    ).subscribe(response => {
      if (response.signals) {
        this._signals.next(response.signals);
        this._error.next(null);
        this._lastRefresh.next(new Date());
      }
      this._loading.next(false);
    });
  }

  getSignalForCoin(coinId: string): Signal | null {
    return this._signals.value[coinId] ?? null;
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
  }
}