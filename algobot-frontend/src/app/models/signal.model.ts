export type SignalType = 'BUY' | 'SELL' | 'HOLD';

export interface Signal {
  coin:              string;
  signal:            SignalType;
  confidence:        number;
  price:             number;
  entry_low:         number;
  entry_high:        number;
  target_price:      number;
  stop_loss_price:   number;
  risk_reward:       number;
  quantity:          number;
  position_value:    number;
  rsi:               number;
  macd_histogram:    number;
  volume_ratio:      number;
  atr:               number;
  reasons:           string[];
  telegram_message:  string;
  timestamp:         string;
  cached_at:         string;
  model_version?:    string;
}

export interface AllSignalsResponse {
  signals:   Record<string, Signal>;
  count:     number;
  timestamp: string;
}

export interface HistoryResponse {
  coin:    string;
  count:   number;
  signals: Signal[];
}

export interface SystemStatus {
  system: string;
  coins:  Record<string, CoinStatus>;
}

export interface CoinStatus {
  model_trained:   boolean;
  data_labeled:    boolean;
  last_signal:     SignalType;
  last_confidence: number;
  last_price:      number;
  cached_at:       string;
}