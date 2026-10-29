import { apiRequest } from "./api";
import {
  AdminDashboardStats,
  GuestQuota,
  TierSpec,
  TokenResponse,
  UserProfile,
} from "../types/auth";

export const authService = {
  getAuthToken(): string | null {
    return localStorage.getItem("auth_token") || localStorage.getItem("access_token");
  },

  setAuthToken(token: string): void {
    localStorage.setItem("auth_token", token);
    localStorage.setItem("access_token", token);
  },

  removeAuthToken(): void {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("access_token");
  },

  async login(identifier: string, password: string): Promise<TokenResponse> {
    const res = await apiRequest<TokenResponse>("/auth/login-json", {
      method: "POST",
      body: JSON.stringify({ identifier, password }),
    });
    this.setAuthToken(res.access_token);
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
    this.setAuthToken(res.access_token);
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

  async forgotPassword(email: string): Promise<{ success: boolean; message: string; otp_debug?: string }> {
    return apiRequest("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  async resetPassword(
    email: string,
    otp_code: string,
    new_password: string
  ): Promise<{ success: boolean; message: string }> {
    return apiRequest("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ email, otp_code, new_password }),
    });
  },

  async getAdminDashboard(): Promise<AdminDashboardStats> {
    return apiRequest<AdminDashboardStats>("/auth/admin/dashboard");
  },

  async adminUpdateTier(user_id: string, tier: string): Promise<{ success: boolean; message: string }> {
    return apiRequest("/auth/admin/update-tier", {
      method: "POST",
      body: JSON.stringify({ user_id, tier }),
    });
  },

  logout(): void {
    this.removeAuthToken();
  },
};
