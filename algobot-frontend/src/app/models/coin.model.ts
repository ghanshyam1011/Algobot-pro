export interface Coin {
  id:      string;   // e.g. 'BTC_USD'
  ticker:  string;   // e.g. 'BTC-USD'
  name:    string;   // e.g. 'Bitcoin'
  symbol:  string;   // e.g. 'BTC'
  color:   string;   // chart colour
}

export const COINS: Coin[] = [
  { id: 'BTC_USD', ticker: 'BTC-USD', name: 'Bitcoin',  symbol: 'BTC', color: '#f7931a' },
  { id: 'ETH_USD', ticker: 'ETH-USD', name: 'Ethereum', symbol: 'ETH', color: '#627eea' },
  { id: 'BNB_USD', ticker: 'BNB-USD', name: 'BNB',      symbol: 'BNB', color: '#f3ba2f' },
  { id: 'SOL_USD', ticker: 'SOL-USD', name: 'Solana',   symbol: 'SOL', color: '#9945ff' },
];

export function getCoin(id: string): Coin {
  return COINS.find(c => c.id === id) ?? COINS[0];
}