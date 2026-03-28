import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  Signal, AllSignalsResponse, HistoryResponse, SystemStatus
} from '../models/signal.model';
import { BacktestResult } from '../models/backtest.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiUrl;

  // ── Health ──────────────────────────────────────────────────────────────────
  health(): Observable<{ status: string; service: string; timestamp: string }> {
    return this.http.get<any>(`${this.base}/`).pipe(catchError(this.handleError));
  }

  // ── Signals ─────────────────────────────────────────────────────────────────
  getAllSignals(): Observable<AllSignalsResponse> {
    return this.http.get<AllSignalsResponse>(`${this.base}/signals/all`)
      .pipe(catchError(this.handleError));
  }

  getSignal(coin: string): Observable<Signal> {
    return this.http.get<Signal>(`${this.base}/signal/${coin}`)
      .pipe(catchError(this.handleError));
  }

  getHistory(coin: string, limit = 100): Observable<HistoryResponse> {
    return this.http.get<HistoryResponse>(
      `${this.base}/history/${coin}?limit=${limit}`
    ).pipe(catchError(this.handleError));
  }

  // ── Backtest ─────────────────────────────────────────────────────────────────
  getBacktest(coin: string): Observable<BacktestResult> {
    return this.http.get<BacktestResult>(`${this.base}/backtest/${coin}`)
      .pipe(catchError(this.handleError));
  }

  // ── Status ───────────────────────────────────────────────────────────────────
  getStatus(): Observable<SystemStatus> {
    return this.http.get<SystemStatus>(`${this.base}/status`)
      .pipe(catchError(this.handleError));
  }

  // ── Error handler ────────────────────────────────────────────────────────────
  private handleError(error: HttpErrorResponse) {
    const msg = error.status === 0
      ? 'Cannot reach AlgoBot API. Is main.py running on port 8000?'
      : `API error ${error.status}: ${error.message}`;
    return throwError(() => new Error(msg));
  }
}