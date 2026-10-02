import { clearToken, getToken } from "./auth";
import { API_URL } from "./config";
import { formatApiErrorDetail } from "./apiError";

export type TimeCategory = "DAY" | "NIGHT";
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
  timestamp: string;
  legs: SlipLeg[];
  betpawa_copy_text: string;
}

export type GenerateOptions = {
  minOdds?: number;
  maxSlips?: number;
  category?: TimeCategory;
  replacePending?: boolean;
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
    const { minOdds = 3, maxSlips = 1, category, replacePending = true } = opts;
    const params = new URLSearchParams({
      min_odds: String(minOdds),
      max_slips: String(maxSlips),
      replace_pending: String(replacePending),
    });
    if (category) params.set("category", category);
    return request<Slip[]>(`/slips/generate?${params}`, { method: "POST" });
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
};

export type HistoryLeg = {
  home_team: string;
  away_team: string;
  odds: number;
  result: "won" | "lost" | "pending";
  home_goals: number | null;
  away_goals: number | null;
  practice: boolean;
};

export type HistorySlip = {
  slip_id: string;
  date: string;
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
