const TOKEN_KEY = "casuya_access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

const SIGNED_OUT_FLAG = "casuya_just_signed_out";

export function markSignedOut(): void {
  sessionStorage.setItem(SIGNED_OUT_FLAG, "1");
}

export function takeSignedOutNotice(): boolean {
  if (typeof window === "undefined") return false;
  const flagged = sessionStorage.getItem(SIGNED_OUT_FLAG) === "1";
  if (flagged) sessionStorage.removeItem(SIGNED_OUT_FLAG);
  return flagged;
}

export function isLoggedIn(): boolean {
  return Boolean(getToken());
}
