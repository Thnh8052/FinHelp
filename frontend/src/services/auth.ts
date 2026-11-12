import { apiRequest } from "./api";
import {
  GuestQuota,
  TierSpec,
  TokenResponse,
  UserProfile,
} from "../types/auth";

// The token lives in a cookie page scripts cannot read. This flag holds no secret: it only spares guests a refused profile request on every page.
const SIGNED_IN_KEY = "finhelp_signed_in";

const remember = (signedIn: boolean) => {
  try {
    if (signedIn) localStorage.setItem(SIGNED_IN_KEY, "1");
    else localStorage.removeItem(SIGNED_IN_KEY);
  } catch {
    /* the browser blocks storage: the profile is simply not asked for */
  }
};

try {
  // Tokens saved by earlier versions must not stay readable.
  localStorage.removeItem("auth_token");
  localStorage.removeItem("access_token");
} catch {
  /* nothing to remove */
}

export const authService = {
  hasSession(): boolean {
    try {
      return localStorage.getItem(SIGNED_IN_KEY) === "1";
    } catch {
      return false;
    }
  },

  forgetSession(): void {
    remember(false);
  },

  async login(identifier: string, password: string): Promise<TokenResponse> {
    const res = await apiRequest<TokenResponse>("/auth/login-json", {
      method: "POST",
      body: JSON.stringify({ identifier, password }),
    });
    remember(true);
    return res;
  },

  async register(
    email: string,
    username: string,
    password: string,
    full_name?: string
  ): Promise<TokenResponse> {
    const res = await apiRequest<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, username, password, full_name }),
    });
    remember(true);
    return res;
  },

  async getMe(): Promise<UserProfile> {
    return apiRequest<UserProfile>("/auth/me");
  },

  async getGuestQuota(): Promise<GuestQuota> {
    return apiRequest<GuestQuota>("/auth/guest-quota");
  },

  async getAllTiers(): Promise<{ success: boolean; tiers: Record<string, TierSpec> }> {
    return apiRequest<{ success: boolean; tiers: Record<string, TierSpec> }>("/auth/tiers");
  },

  async forgotPassword(email: string): Promise<{ success: boolean }> {
    return apiRequest("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  async resetPassword(
    email: string,
    otp_code: string,
    new_password: string
  ): Promise<{ success: boolean }> {
    return apiRequest("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ email, otp_code, new_password }),
    });
  },

  async adminUpdateTier(user_id: string, tier: string): Promise<{ success: boolean }> {
    return apiRequest("/auth/admin/update-tier", {
      method: "POST",
      body: JSON.stringify({ user_id, tier }),
    });
  },

  async logout(): Promise<void> {
    remember(false);
    await apiRequest("/auth/logout", { method: "POST" }).catch(() => undefined);
  },
};
