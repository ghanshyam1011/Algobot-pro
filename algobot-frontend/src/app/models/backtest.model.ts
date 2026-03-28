export interface BacktestResult {
  coin:               string;
  total_trades:       number;
  win_rate_pct:       number;
  total_return_pct:   number;
  max_drawdown_pct:   number;
  sharpe_ratio:       number;
  profit_factor:      number;
  initial_capital:    number;
  final_capital:      number;
}

export interface TradeLogEntry {
  dir:         string;
  pnl:         number;
  dur:         number;
  entry_price?: number;
  exit_price?:  number;
  timestamp?:   string;
}