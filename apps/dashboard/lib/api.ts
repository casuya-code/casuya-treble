import { clearToken, getToken } from "./auth";
import { API_URL } from "./config";
import { formatApiErrorDetail } from "./apiError";

export type TimeCategory = "DAY" | "NIGHT" | "T00_06" | "T06_12" | "T12_18" | "T18_24" | "ALL_DAY";
export type SlipStatus = "PENDING" | "LIVE" | "WON" | "LOST";

export interface SlipLeg {
  fixture_id: string;
  home_team: string;
  away_team: string;
  league: string;
  kickoff_at: string;
  market: string;
  leg_odds: number;
  model_probability: number;
  edge: number | null;
  is_demo?: boolean;
  home_goals?: number | null;
  away_goals?: number | null;
  fh_corners?: number | null;
  fh_half_complete?: boolean;
  match_finished?: boolean;
}

export interface Slip {
  slip_id: string;
  time_category: TimeCategory;
  model_probability: number;
  closing_odds: number;
  implied_probability: number;
  edge: number | null;
  status: SlipStatus;
  placed_on_betpawa: boolean;
  forced?: boolean;
  timestamp: string;
  legs: SlipLeg[];
  betpawa_copy_text: string;
}

export type WeatherNote = { match: string; reason: "rain" | "snow" | "wind" | string };

export type GenerateResult = {
  slips: Slip[];
  reason:
    | "none_loaded"
    | "all_started"
    | "no_price"
    | "too_few"
    | "spread_days"
    | "below_floor"
    | "below_min"
    | "weather"
    | "no_corner"
    | null;
  stored: number;
  upcoming: number;
  priced: number;
  same_day: number;
  weather?: WeatherNote[];
};

export type GenerateOptions = {
  /** Combined odds floor for a generated slip. Default 2.1. */
  minOdds?: number;
  /** Combined odds ceiling for a generated slip. Default 2.5. */
  maxOdds?: number;
  /** Teams per slip: 1, 2, or 3. Default 3. */
  maxLegs?: number;
  maxSlips?: number;
  replacePending?: boolean;
  /** One market, or both together so a slip can mix legs. */
  market?: "goals" | "corners" | Array<"goals" | "corners">;
};

export type AuthUser = { id: string; email: string; is_admin: boolean };

export type AdminUser = {
  id: string;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  slip_count: number;
};

export type AdminOverview = {
  users: number;
  active_users: number;
  admins: number;
  fixtures: number;
  slips: number;
};
export type TokenResponse = { access_token: string; token_type: string; user: AuthUser };

async function request<T>(path: string, init?: RequestInit, auth = true): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (res.status === 401 && auth) {
    clearToken();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      const raw = body.detail ?? body.message ?? body;
      detail = formatApiErrorDetail(raw);
    } catch {
      detail = await res.text();
    }
    throw new Error(detail || "Request failed");
  }
  return res.json() as Promise<T>;
}

export type HealthResponse = {
  status: string;
  version?: string;
  database?: string;
  odds_api?: string;
};

export type OddsProviderStatus = {
  configured: boolean;
  default_sport: string;
  default_region: string;
  docs_url: string;
};

export type BetPawaSourceStatus = {
  configured: boolean;
  brand: string;
  base_url: string;
  verify_url: string;
};

export type BbGateInfo = { gate: string; label: string; threshold: string };
export type BbCheck = { passed: boolean; reason: string };
export type BbTipStatus = "PENDING" | "WON" | "LOST" | "PUSH" | "AUTOMATED_REJECTED";
export type BbTip = {
  id: string;
  status: BbTipStatus;
  pick: string;
  line: number;
  over_odds: number | null;
  model_total: number;
  p_over: number;
  edge: number;
  created_at: string;
  settled_at: string | null;
  notes: string | null;
};
export type BbGateRun = {
  passed: boolean;
  passed_count: number;
  ran_at: string;
  checks: Record<string, BbCheck> | null;
};
export type BbGame = {
  id: string;
  espn_event_id: string;
  tipoff_at: string;
  home_team: string;
  away_team: string;
  status: string;
  home_score: number | null;
  away_score: number | null;
  model: { total: number | null; p_over: number | null; edge: number | null } | null;
  market_total: number | null;
  result: "over" | "under" | "push" | null;
  gate_run: BbGateRun | null;
  tip: BbTip | null;
};
export type BbHealth = {
  status: string;
  enabled: boolean;
  date: string;
  games_today: number;
  pending_tips: number;
  last_scan_at: string | null;
  last_scan_stats: Record<string, number | boolean | string | null> | null;
  lock_minutes: number;
  scan_minutes: number;
  backfill: string;
};
export type BbGates = { gates: BbGateInfo[]; policy: string };
export type BbAudit = {
  window_days: number;
  tips: number;
  won: number;
  lost: number;
  push: number;
  pending: number;
  rejected: number;
  hit_rate: number | null;
  clv: { n: number; avg_points: number | null; beat_close_pct: number | null };
};
export type BbSlate = { date: string; count: number; games: BbGame[] };
export type BbShadowRule = {
  key: string;
  label: string;
  n: number;
  won: number;
  lost: number;
  push: number;
  hit_rate: number | null;
  roi: number | null;
  roi_n: number;
  clv_n: number;
  avg_clv: number | null;
  beat_close_pct: number | null;
};
export type BbShadow = { games: number; rules: BbShadowRule[]; note: string };
export type BbBacktest = { model_rows: number; candidate_rules: BbShadowRule[] };

export const api = {
  health: () => request<HealthResponse>("/health", undefined, false),
  register: (email: string, password: string) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }, false),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }, false),
  me: () => request<AuthUser>("/auth/me"),
  adminOverview: () => request<AdminOverview>("/admin/overview"),
  adminUsers: () => request<AdminUser[]>("/admin/users"),
  setUserActive: (userId: string, is_active: boolean) =>
    request<AdminUser>(`/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active }),
    }),
  forgotPassword: (email: string) =>
    request<{ message: string; reset_link?: string | null }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }, false),
  resetPassword: (token: string, new_password: string) =>
    request<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password }),
    }, false),
  oddsProviderStatus: () => request<OddsProviderStatus>("/odds/provider/status"),
  betpawaStatus: () => request<BetPawaSourceStatus>("/ingestion/betpawa/status"),
  importBetPawa: (opts?: { take?: number; popularOnly?: boolean }) => {
    const params = new URLSearchParams();
    if (opts?.take != null) params.set("take", String(opts.take));
    if (opts?.popularOnly) params.set("popular_only", "true");
    const q = params.toString();
    return request<{
      imported: number;
      updated: number;
      events_fetched: number;
      practice_removed: number;
      history_imported?: number;
      history_updated?: number;
    }>(
      `/ingestion/import/betpawa${q ? `?${q}` : ""}`,
      { method: "POST" }
    );
  },
  importOddsApi: () =>
    request<{ imported: number; updated: number; requests_remaining: string }>(
      "/odds/import/the-odds-api",
      { method: "POST" }
    ),
  seedDemo: () => request<{ id: string }[]>("/ingestion/fixtures/seed-demo", { method: "POST" }),
  generateSlips: (opts: GenerateOptions = {}) => {
    const {
      minOdds = 2.1,
      maxOdds = 2.5,
      maxLegs = 3,
      maxSlips = 1,
      replacePending = true,
      market = "goals",
    } = opts;
    const requested = Array.isArray(market) ? market : [market];
    const markets = requested.length ? requested : ["goals" as const];
    const params = new URLSearchParams({
      min_odds: String(minOdds),
      max_odds: String(maxOdds),
      max_legs: String(maxLegs),
      max_slips: String(maxSlips),
      replace_pending: String(replacePending),
    });
    for (const value of markets) params.append("market", value);
    return request<GenerateResult>(`/slips/generate?${params}`, { method: "POST" });
  },
  listSlips: (opts?: { days?: number; status?: SlipStatus }) => {
    const params = new URLSearchParams();
    if (opts?.days != null) params.set("days", String(opts.days));
    if (opts?.status) params.set("status", opts.status);
    const q = params.toString();
    return request<Slip[]>(`/slips${q ? `?${q}` : ""}`);
  },
  retentionDays: () => request<{ retention_days: number }>("/slips/retention"),
  markPlaced: (slipId: string, placed: boolean) =>
    request<Slip>(`/slips/${slipId}/placed`, {
      method: "PATCH",
      body: JSON.stringify({ placed_on_betpawa: placed }),
    }),
  syncStatus: () => request<{ slips_updated: number }>("/slips/sync-status", { method: "POST" }),
  publicHistory: () => request<PublicHistory>("/slips/history", undefined, false),
  recordVisit: (visitorId: string) =>
    request<VisitTotals>("/visits", { method: "POST", body: JSON.stringify({ visitor_id: visitorId }) }, false),
  bbHealth: () => request<BbHealth>("/btips/health"),
  bbGates: () => request<BbGates>("/btips/gates"),
  bbGames: (date?: string) =>
    request<BbSlate>(`/btips/games${date ? `?date=${encodeURIComponent(date)}` : ""}`),
  bbAudit: (windowDays = 30) => request<BbAudit>(`/btips/audit?window_days=${windowDays}`),
  bbShadow: () => request<BbShadow>("/btips/shadow"),
  bbBacktest: () => request<BbBacktest>("/btips/backtest"),
};

export type VisitTotals = {
  today: number;
  yesterday: number;
  week: number;
  year: number;
};

export type HistoryLeg = {
  home_team: string;
  away_team: string;
  odds: number;
  result: "won" | "lost" | "pending";
  market?: string;
  home_goals: number | null;
  away_goals: number | null;
  fh_corners?: number | null;
  practice: boolean;
};

export type HistorySlip = {
  slip_id: string;
  date: string;
  forced?: boolean;
  result: "won" | "lost" | "pending";
  combined_odds: number;
  profit: number | null;
  legs: HistoryLeg[];
};

export type HistoryDay = {
  date: string;
  matches_won: number;
  matches_lost: number;
  single_profit: number;
  trebles_placed: number;
  trebles_won: number;
  trebles_lost: number;
  trebles_pending: number;
  treble_profit: number;
};

export type PublicHistory = {
  stake: number;
  matches_won: number;
  matches_lost: number;
  matches_pending: number;
  trebles_placed: number;
  trebles_won: number;
  trebles_lost: number;
  trebles_pending: number;
  single_profit: number;
  treble_profit: number;
  days: HistoryDay[];
  slips: HistorySlip[];
};
