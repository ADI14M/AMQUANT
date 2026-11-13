const API_BASE =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.PROD ? 'https://amquant-api.onrender.com' : 'http://localhost:8000')

export interface SavedScenario {
  id: string
  user_id: string
  title: string
  module_name: 'foundations' | 'bayesian' | 'stochastic' | 'options' | 'intelligence' | 'india'
  scenario_data: Record<string, any>
  created_at: string
  updated_at: string
}

export interface ResearchHistoryEntry {
  id: string
  user_id: string
  module_name: 'foundations' | 'bayesian' | 'stochastic' | 'options' | 'intelligence' | 'india'
  scenario_id: string | null
  summary: Record<string, any>
  created_at: string
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/api/health`)
    return response.ok
  } catch {
    return false
  }
}

let inMemoryAccessSessionToken: string | null = null

export function setAccessSessionToken(token: string | null) {
  inMemoryAccessSessionToken = token
}

export function getAccessSessionToken(): string | null {
  return inMemoryAccessSessionToken
}

export async function securedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers || {})
  const token = getAccessSessionToken()
  if (token && !headers.has('X-Amquant-Access-Token')) {
    headers.set('X-Amquant-Access-Token', token)
  }
  return fetch(input, {
    ...init,
    headers,
    credentials: 'include',
  })
}

function authHeaders(token: string | null | undefined, extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const sessionToken = getAccessSessionToken()
  if (sessionToken && !headers['X-Amquant-Access-Token']) {
    headers['X-Amquant-Access-Token'] = sessionToken
  }
  return headers
}

// ============================================================================
// SCENARIOS API
// ============================================================================

export async function listSavedScenarios(token: string, moduleName?: string): Promise<SavedScenario[]> {
  const query = moduleName ? `?module_name=${encodeURIComponent(moduleName)}` : ''
  const res = await securedFetch(`${API_BASE}/api/scenarios${query}`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to list scenarios')
  }
  return res.json() as Promise<SavedScenario[]>
}

export async function getSavedScenario(token: string, scenarioId: string): Promise<SavedScenario> {
  const res = await securedFetch(`${API_BASE}/api/scenarios/${scenarioId}`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Scenario not found')
  }
  return res.json() as Promise<SavedScenario>
}

export async function createSavedScenario(
  token: string,
  title: string,
  moduleName: string,
  scenarioData: Record<string, any>
): Promise<SavedScenario> {
  const res = await securedFetch(`${API_BASE}/api/scenarios`, {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      title: title.trim(),
      module_name: moduleName,
      scenario_data: scenarioData,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to save scenario')
  }
  return res.json() as Promise<SavedScenario>
}

export async function updateSavedScenario(
  token: string,
  scenarioId: string,
  title?: string,
  scenarioData?: Record<string, any>
): Promise<SavedScenario> {
  const body: Record<string, any> = {}
  if (title !== undefined) body.title = title.trim()
  if (scenarioData !== undefined) body.scenario_data = scenarioData

  const res = await securedFetch(`${API_BASE}/api/scenarios/${scenarioId}`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to update scenario')
  }
  return res.json() as Promise<SavedScenario>
}

export async function deleteSavedScenario(token: string, scenarioId: string): Promise<void> {
  const res = await securedFetch(`${API_BASE}/api/scenarios/${scenarioId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to delete scenario')
  }
}

// ============================================================================
// RESEARCH HISTORY API
// ============================================================================

export async function listResearchHistory(token: string, limit = 50, offset = 0): Promise<ResearchHistoryEntry[]> {
  const res = await securedFetch(`${API_BASE}/api/research-history?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to list research history')
  }
  return res.json() as Promise<ResearchHistoryEntry[]>
}

export async function recordResearchHistory(
  token: string,
  moduleName: string,
  summary: Record<string, any>,
  scenarioId?: string | null
): Promise<ResearchHistoryEntry> {
  const res = await securedFetch(`${API_BASE}/api/research-history`, {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      module_name: moduleName,
      summary,
      scenario_id: scenarioId ?? null,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to record research history')
  }
  return res.json() as Promise<ResearchHistoryEntry>
}

export async function deleteResearchHistoryEntry(token: string, historyId: string): Promise<void> {
  const res = await securedFetch(`${API_BASE}/api/research-history/${historyId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to delete history entry')
  }
}

export async function clearResearchHistory(token: string): Promise<void> {
  const res = await securedFetch(`${API_BASE}/api/research-history`, {
    method: 'DELETE',
    headers: authHeaders(token),
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to clear research history')
  }
}


// ============================================================================
// AMQUANT INDIA API
// ============================================================================

export interface IndiaInstrument {
  symbol: string
  exchange: 'NSE' | 'BSE'
  isin: string
  company_name: string
  instrument_type: 'EQUITY' | 'INDEX' | 'ETF' | 'FUT' | 'OPT'
  sector: string
  market_cap_category: 'LARGE_CAP' | 'MID_CAP' | 'SMALL_CAP' | 'BROAD_MARKET'
  tick_size: number
  lot_size: number
  has_derivatives: boolean
  yahoo_ticker: string
  listing_date?: string
  is_active?: boolean
  delisting_date?: string
}

export interface IndiaMarketOverview {
  macro_snapshot: {
    rbi_repo_rate: number
    india_10y_gsec_yield: number
    t_bill_91d_yield: number
    cpi_inflation: number
    usd_inr_rate: number
    india_vix: number
    as_of_date: string
    provenance_source: string
  }
  macro_history: Array<{
    period: string
    repo_rate: number
    gsec_10y: number
    cpi: number
    usd_inr: number
    vix: number
  }>
  headline_quotes: Array<{
    symbol: string
    ticker: string
    price: number
    previous_close: number
    change: number
    change_pct: number
    currency: string
    exchange: string
  }>
  market_breadth: {
    total_analyzed: number
    advances: number
    declines: number
    unchanged: number
    advance_decline_ratio: number
    pct_above_50d_sma: number
    pct_above_200d_sma: number
  }
}

export async function getIndiaInstruments(params?: {
  exchange?: string
  instrument_type?: string
  sector?: string
  market_cap_category?: string
  query?: string
}): Promise<IndiaInstrument[]> {
  const url = new URL(`${API_BASE}/api/india/instruments`)
  if (params?.exchange) url.searchParams.set('exchange', params.exchange)
  if (params?.instrument_type) url.searchParams.set('instrument_type', params.instrument_type)
  if (params?.sector) url.searchParams.set('sector', params.sector)
  if (params?.market_cap_category) url.searchParams.set('market_cap_category', params.market_cap_category)
  if (params?.query) url.searchParams.set('query', params.query)

  const res = await securedFetch(url.toString())
  if (!res.ok) throw new Error('Failed to fetch Indian instruments catalog')
  return res.json() as Promise<IndiaInstrument[]>
}

export async function getIndiaMarketOverview(): Promise<IndiaMarketOverview> {
  const res = await securedFetch(`${API_BASE}/api/india/market-overview`)
  if (!res.ok) throw new Error('Failed to fetch Indian market overview')
  return res.json() as Promise<IndiaMarketOverview>
}

export async function getIndiaDataCoverage(): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/data-coverage`)
  if (!res.ok) throw new Error('Failed to fetch data coverage audit')
  return res.json()
}

export async function getIndiaHistory(symbol: string, period = '1y'): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/history/${encodeURIComponent(symbol)}?period=${period}`)
  if (!res.ok) throw new Error(`Failed to fetch history for ${symbol}`)
  return res.json()
}

export async function runBayesianRegimeExperiment(payload: {
  symbol: string
  mu_bull?: number
  mu_bear?: number
  mu_neut?: number
  sigma_bull?: number
  sigma_bear?: number
  regime_persistence?: number
  entry_threshold?: number
}): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/experiment/bayesian-regime`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Bayesian regime experiment failed')
  }
  return res.json()
}

export async function runIndiaBacktest(payload: {
  symbol: string
  strategy_type: 'SMA_CROSS' | 'MOMENTUM'
  fast_period: number
  slow_period: number
  initial_capital: number
}): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/backtest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Backtest execution failed')
  }
  return res.json()
}

// ── Phase 2: Historical Data Manager API ─────────────────────────

export async function getIndiaUniverseStats(): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/universe-stats`)
  if (!res.ok) throw new Error('Failed to fetch universe stats')
  return res.json()
}

export async function getHistoryManagerCoverage(): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/history-manager/coverage`)
  if (!res.ok) throw new Error('Failed to fetch history coverage')
  return res.json()
}

export async function startHistoryDownload(payload: {
  symbols?: string[]
  exchange?: string
  instrument_type?: string
  market_cap_category?: string
  period?: string
  incremental?: boolean
}): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/history-manager/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Historical download failed')
  }
  return res.json()
}

export async function getIndiaCorporateActions(symbol: string): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/corporate-actions/${encodeURIComponent(symbol)}`)
  if (!res.ok) throw new Error(`Failed to fetch corporate actions for ${symbol}`)
  return res.json()
}

export async function getIndiaSeriesComparison(symbol: string): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/series-comparison/${encodeURIComponent(symbol)}`)
  if (!res.ok) throw new Error(`Failed to fetch series comparison for ${symbol}`)
  return res.json()
}

// ── Phase 3: Professional Backtesting API ────────────────────────

export interface BacktestStrategyInfo {
  id: string
  name: string
  description: string
  entry_rule: string
  exit_rule: string
  parameters: Array<{
    name: string
    display_name: string
    param_type: string
    default_value: any
    min_value?: number
    max_value?: number
    step?: number
    description: string
  }>
  current_params: Record<string, any>
}

export interface AdvancedBacktestRequest {
  strategy_id: string
  strategy_params?: Record<string, any>
  symbols: string[]
  initial_capital?: number
  start_date?: string | null
  end_date?: string | null
  sizing_type?: 'PERCENT_OF_EQUITY' | 'FIXED_AMOUNT' | 'FIXED_SHARES'
  sizing_value?: number
  max_concurrent_positions?: number
  stop_loss_pct?: number | null
  take_profit_pct?: number | null
  trailing_stop_pct?: number | null
  slippage_bps?: number
  benchmark_symbol?: string
}

export async function getIndiaBacktestStrategies(): Promise<BacktestStrategyInfo[]> {
  const res = await securedFetch(`${API_BASE}/api/india/backtest/strategies`)
  if (!res.ok) throw new Error('Failed to fetch backtest strategies catalog')
  return res.json() as Promise<BacktestStrategyInfo[]>
}

export async function runAdvancedIndiaBacktest(payload: AdvancedBacktestRequest): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/backtest/run-advanced`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Advanced backtest execution failed')
  }
  return res.json()
}

// ─────────────────────────────────────────────────────────────────────
// PHASE 4: INTRADAY DATA & F&O DERIVATIVES MARKET DATA
// ─────────────────────────────────────────────────────────────────────

export interface ProviderSpecification {
  provider_id: string
  name: string
  auth_requirements: string
  historical_depth_daily: string
  historical_depth_intraday: string
  supported_intervals: string[]
  rate_limits: string
  cost_inr_gbp: string
  licensing_restrictions: string
  status: string
  notes: string
}

export interface IntradayQualityReport {
  symbol: string
  interval: string
  total_bars: number
  total_sessions: number
  start_timestamp: string
  end_timestamp: string
  overall_completeness_pct: number
  total_missing_bars: number
  duplicate_bars_removed: number
  out_of_session_bars_filtered: number
  sessions_audit: Array<{
    date: string
    bars_found: number
    bars_expected: number
    completeness_pct: number
    first_candle_time: string
    last_candle_time: string
    is_complete: boolean
    missing_bars_count: number
  }>
  provider: string
}

export interface IntradayHistoryResponse {
  symbol: string
  interval: string
  total_bars: number
  series: any[]
  quality_report: IntradayQualityReport
}

export interface DerivativesContract {
  symbol: string
  underlying_symbol: string
  exchange: string
  contract_type: 'FUTIDX' | 'FUTSTK' | 'OPTIDX' | 'OPTSTK'
  expiry_date: string
  strike_price: number
  option_type: 'CE' | 'PE' | null
  lot_size: number
  tick_size: number
  listing_date: string
  last_trading_date: string
  is_active: boolean
}

export interface LotSizesResponse {
  underlying: string
  current_lot_size: number
  revisions_count: number
  history: Array<{
    underlying: string
    start_date: string
    end_date: string
    lot_size: number
  }>
  regulatory_notes: string
}

export interface ContinuousFuturesResponse {
  underlying: string
  method: string
  is_continuous: boolean
  execution_disclaimer: string
  total_bars: number
  start_date: string
  end_date: string
  rollover_events: Array<{
    roll_date: string
    from_contract: string
    to_contract: string
    near_close: number
    next_close: number
    roll_spread: number
    ratio: number
  }>
  series: any[]
}

export interface OptionQuote {
  strike: number
  option_type: 'CE' | 'PE'
  last_price: number
  open: number
  high: number
  low: number
  close: number
  volume: number
  open_interest: number
  lot_size: number
  iv: number
  delta: number
  gamma: number
  theta: number
  vega: number
  is_model_estimate: boolean
}

export interface OptionChainRow {
  strike: number
  call: OptionQuote | null
  put: OptionQuote | null
  is_atm: boolean
}

export interface OptionChainResponse {
  underlying: string
  underlying_price: number
  as_of_date: string
  expiry_date: string
  days_to_expiry: number
  pcr_oi: number
  pcr_volume: number
  max_pain_strike: number
  total_call_oi: number
  total_put_oi: number
  total_call_volume: number
  total_put_volume: number
  strikes: OptionChainRow[]
  disclaimer: string
}

export async function getIndiaIntradayHistory(
  symbol: string,
  interval: string = '5m',
  limit: number = 375,
): Promise<IntradayHistoryResponse> {
  const res = await securedFetch(`${API_BASE}/api/india/intraday/history?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`)
  if (!res.ok) throw new Error('Failed to fetch intraday history')
  return res.json()
}

export async function downloadIndiaIntraday(payload: {
  symbol: string
  interval: string
  period?: string
  start_date?: string | null
  end_date?: string | null
}): Promise<any> {
  const res = await securedFetch(`${API_BASE}/api/india/intraday/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to download intraday data')
  }
  return res.json()
}

export async function getIndiaDerivativesContracts(
  underlying?: string,
  contract_type?: string,
  expiry?: string,
): Promise<DerivativesContract[]> {
  const params = new URLSearchParams()
  if (underlying) params.append('underlying', underlying)
  if (contract_type) params.append('contract_type', contract_type)
  if (expiry) params.append('expiry', expiry)
  const res = await securedFetch(`${API_BASE}/api/india/derivatives/contracts?${params.toString()}`)
  if (!res.ok) throw new Error('Failed to fetch derivatives contracts')
  return res.json()
}

export async function getIndiaDerivativesLotSizes(underlying: string = 'NIFTY 50'): Promise<LotSizesResponse> {
  const res = await securedFetch(`${API_BASE}/api/india/derivatives/lot-sizes?underlying=${encodeURIComponent(underlying)}`)
  if (!res.ok) throw new Error('Failed to fetch lot sizes')
  return res.json()
}

export async function getIndiaContinuousFutures(
  underlying: string = 'NIFTY 50',
  method: string = 'BACK_ADJUSTED_DIFFERENCE',
): Promise<ContinuousFuturesResponse> {
  const res = await securedFetch(`${API_BASE}/api/india/derivatives/futures/continuous?underlying=${encodeURIComponent(underlying)}&method=${method}`)
  if (!res.ok) throw new Error('Failed to fetch continuous futures')
  return res.json()
}

export async function getIndiaOptionChain(
  underlying: string = 'NIFTY 50',
  expiry?: string,
): Promise<OptionChainResponse> {
  const params = new URLSearchParams()
  params.append('underlying', underlying)
  if (expiry) params.append('expiry', expiry)
  const res = await securedFetch(`${API_BASE}/api/india/derivatives/options/chain?${params.toString()}`)
  if (!res.ok) throw new Error('Failed to fetch option chain')
  return res.json()
}

export async function getIndiaProviders(): Promise<ProviderSpecification[]> {
  const res = await securedFetch(`${API_BASE}/api/india/providers`)
  if (!res.ok) throw new Error('Failed to fetch providers catalog')
  return res.json()
}

// ─────────────────────────────────────────────────────────────────────
// PHASE 5: INTRADAY, FUTURES & OPTIONS BACKTESTING ENGINES
// ─────────────────────────────────────────────────────────────────────

export interface IntradayStrategyParamMeta {
  type: string
  default: any
  min?: number
  max?: number
  step?: number
  description: string
}

export interface IntradayStrategyMeta {
  id: string
  name: string
  description: string
  parameters: Record<string, IntradayStrategyParamMeta>
  higher_timeframe_supported: boolean
}

export interface IntradayBacktestRequest {
  strategy_id: string
  symbol: string
  timeframe?: string
  start_date?: string
  end_date?: string
  initial_capital?: number
  position_sizing_pct?: number
  allow_short?: boolean
  stop_loss_pct?: number | null
  take_profit_pct?: number | null
  trailing_stop_pct?: number | null
  parameters?: Record<string, any>
  use_higher_timeframe_filter?: boolean
  walk_forward?: boolean
  in_sample_ratio?: number
}

export interface IntradayBacktestTrade {
  trade_id: string
  symbol: string
  direction: string
  entry_time: string
  entry_price: number
  exit_time: string
  exit_price: number
  quantity: number
  gross_pnl: number
  total_costs: number
  net_pnl: number
  return_pct: number
  exit_reason: string
  bars_held: number
}

export interface IntradayBacktestResponse {
  config: Record<string, any>
  trades: IntradayBacktestTrade[]
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  profit_factor: number
  gross_pnl: number
  total_costs: number
  net_pnl: number
  return_on_capital: number
  max_drawdown_pct: number
  max_drawdown_amount: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  average_trade_pnl: number
  avg_win: number
  avg_loss: number
  largest_win: number
  largest_loss: number
  equity_curve: Array<{ datetime: string; equity: number; cash: number; drawdown_pct: number }>
  walk_forward_metrics?: {
    in_sample: Record<string, any>
    out_of_sample: Record<string, any>
    in_sample_bars: number
    out_of_sample_bars: number
    sharpe_degradation_pct: number
  }
}

export interface FuturesBacktestRequest {
  underlying: string
  start_date?: string
  end_date?: string
  initial_capital?: number
  num_lots?: number
  days_before_expiry_roll?: number
  margin_requirement_pct?: number
  strategy_type?: string
  sma_fast?: number
  sma_slow?: number
}

export interface FuturesBacktestResponse {
  config: Record<string, any>
  trades: Array<{
    contract_symbol: string
    underlying: string
    direction: string
    entry_date: string
    entry_price: number
    exit_date: string
    exit_price: number
    lot_size: number
    num_lots: number
    total_quantity: number
    gross_pnl: number
    total_costs: number
    net_pnl: number
    exit_reason: string
    roll_spread: number
    basis_at_entry: number
  }>
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  profit_factor: number
  gross_pnl: number
  total_costs: number
  net_pnl: number
  total_rollover_costs: number
  return_on_capital: number
  max_drawdown_pct: number
  sharpe_ratio: number
  equity_curve: Array<{ date: string; equity: number; cash: number; mtm_pnl: number; margin_locked: number }>
  rollover_log: Array<{ date: string; old_contract: string; new_contract: string; roll_spread: number; roll_cost: number }>
}

export interface OptionLegMeta {
  action: 'BUY' | 'SELL'
  option_type: 'CE' | 'PE'
  strike: number
  entry_premium: number
  lot_size: number
  num_lots: number
  total_quantity: number
  exit_premium?: number
  implied_volatility: number
  is_theoretical: boolean
  delta: number
  gamma: number
  theta: number
  vega: number
}

export interface OptionsStrategyTemplate {
  id: string
  name: string
  type: string
  description: string
  legs: Array<{
    action: 'BUY' | 'SELL'
    option_type: 'CE' | 'PE'
    strike_offset: number
  }>
}

export interface OptionsBacktestRequest {
  strategy_id: string
  underlying?: string
  entry_date?: string
  expiry_date?: string
  initial_capital?: number
  num_lots?: number
  strike_step?: number
  underlying_entry_spot?: number
  underlying_exit_spot?: number
  exit_date?: string | null
  days_to_expiry_entry?: number
  days_to_expiry_exit?: number
  volatility?: number
  custom_legs?: Array<Record<string, any>> | null
}

export interface OptionsBacktestResponse {
  config: Record<string, any>
  legs: OptionLegMeta[]
  payoff: {
    spot_price: number
    points: Array<{ spot: number; pct_change: number; total_pnl: number }>
    max_profit: number | string
    max_loss: number | string
    breakevens: number[]
    risk_reward_ratio: number | null
    net_debit_or_credit: number
    margin_required: number
    net_delta: number
    net_gamma: number
    net_theta: number
    net_vega: number
  }
  gross_pnl: number
  transaction_costs: number
  net_pnl: number
  roi_on_capital: number
  roi_on_margin: number
  margin_required: number
  is_theoretical_simulation: boolean
  summary: string
  disclaimer: string
}

export async function getIntradayStrategiesCatalog(): Promise<IntradayStrategyMeta[]> {
  const res = await securedFetch(`${API_BASE}/api/india/backtest/intraday/strategies`)
  if (!res.ok) throw new Error('Failed to fetch intraday strategies catalog')
  return res.json()
}

export async function runIntradayBacktest(req: IntradayBacktestRequest): Promise<IntradayBacktestResponse> {
  const res = await securedFetch(`${API_BASE}/api/india/backtest/intraday`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Intraday backtest execution failed')
  }
  return res.json()
}

export async function runFuturesBacktest(req: FuturesBacktestRequest): Promise<FuturesBacktestResponse> {
  const res = await securedFetch(`${API_BASE}/api/india/backtest/futures`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Futures backtest execution failed')
  }
  return res.json()
}

export async function getOptionsStrategiesCatalog(): Promise<OptionsStrategyTemplate[]> {
  const res = await securedFetch(`${API_BASE}/api/india/backtest/options/strategies`)
  if (!res.ok) throw new Error('Failed to fetch options strategies catalog')
  return res.json()
}

export async function runOptionsBacktest(req: OptionsBacktestRequest): Promise<OptionsBacktestResponse> {
  const res = await securedFetch(`${API_BASE}/api/india/backtest/options`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Options backtest execution failed')
  }
  return res.json()
}

// ============================================================================
// ACCESS & ADMIN API
// ============================================================================

export interface AccessVerifyResponse {
  ok: boolean
  session_token: string
  expires_at: string
  detail?: string
}

export interface AccessStatusResponse {
  authenticated: boolean
  expires_at?: number
  role?: string
}

export interface SecurityEvent {
  id: string
  timestamp: string
  event_type: string
  client_ip: string
  detail: string
  metadata: Record<string, any>
}

export interface SecurityLogsResponse {
  count: number
  events: SecurityEvent[]
}

export interface AdminSystemStatusResponse {
  owner_email: string
  active_password_configured: boolean
  password_hash_preview: string
  rate_limiter_status: Record<string, any>
  storage_directory: string
  disk_usage: Record<string, any>
}

export async function verifyAccessPassword(password: string): Promise<AccessVerifyResponse> {
  const res = await fetch(`${API_BASE}/api/auth/access/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    const retryAfter = res.headers.get('Retry-After')
    const message = err?.detail || 'Incorrect access password.'
    const error: any = new Error(message)
    error.status = res.status
    error.retryAfter = retryAfter ? parseInt(retryAfter, 10) : undefined
    throw error
  }
  const data = (await res.json()) as AccessVerifyResponse
  setAccessSessionToken(data.session_token)
  return data
}

export async function checkAccessStatus(): Promise<AccessStatusResponse> {
  try {
    const headers: Record<string, string> = {}
    const token = getAccessSessionToken()
    if (token) {
      headers['X-Amquant-Access-Token'] = token
    }
    const res = await fetch(`${API_BASE}/api/auth/access/status`, {
      headers,
      credentials: 'include',
    })
    if (!res.ok) return { authenticated: false }
    return (await res.json()) as AccessStatusResponse
  } catch {
    return { authenticated: false }
  }
}

export async function revokeAccessSession(): Promise<void> {
  try {
    const headers: Record<string, string> = {}
    const token = getAccessSessionToken()
    if (token) {
      headers['X-Amquant-Access-Token'] = token
    }
    await fetch(`${API_BASE}/api/auth/access/revoke`, {
      method: 'POST',
      headers,
      credentials: 'include',
    })
  } finally {
    setAccessSessionToken(null)
  }
}

export async function getSecurityLogs(userJwt: string, limit: number = 100): Promise<SecurityLogsResponse> {
  const res = await securedFetch(`${API_BASE}/api/admin/security-logs?limit=${limit}`, {
    headers: { Authorization: `Bearer ${userJwt}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to retrieve security logs')
  }
  return res.json() as Promise<SecurityLogsResponse>
}

export async function rotateAccessPassword(
  userJwt: string,
  newPassword: string,
): Promise<{ ok: boolean; detail: string; hash_preview: string }> {
  const res = await securedFetch(`${API_BASE}/api/admin/rotate-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${userJwt}` },
    body: JSON.stringify({ new_password: newPassword }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to rotate access password')
  }
  return res.json()
}

export async function revokeAllAccessSessions(userJwt: string): Promise<{ ok: boolean; detail: string }> {
  const res = await securedFetch(`${API_BASE}/api/admin/revoke-all-sessions`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${userJwt}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to revoke sessions')
  }
  return res.json()
}

export async function getAdminSystemStatus(userJwt: string): Promise<AdminSystemStatusResponse> {
  const res = await securedFetch(`${API_BASE}/api/admin/system-status`, {
    headers: { Authorization: `Bearer ${userJwt}` },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || 'Failed to retrieve system status')
  }
  return res.json() as Promise<AdminSystemStatusResponse>
}



