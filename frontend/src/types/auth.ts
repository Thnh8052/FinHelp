export interface UserQuota {
  tier: "guest" | "user" | "admin";
  daily_messages_limit: number;
  messages_used_today: number;
  max_upload_documents: number;
  max_file_size_mb: number;
  total_tokens_consumed: number;
}

export interface UserProfile {
  user_id: string;
  email: string;
  username: string;
  full_name: string | null;
  role: "user" | "admin";
  quota: UserQuota;
  is_active: boolean;
  created_at?: string;
  last_login_at?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
  full_name: string | null;
  role: "user" | "admin";
  tier: string;
}

export interface GuestQuota {
  is_authenticated: boolean;
  tier: string;
  max_upload_documents: number;
  max_file_size_mb: number;
  cost_description?: string;
}

export interface TierSpec {
  tier_name: string;
  daily_messages_limit: number;
  max_upload_documents: number;
  max_file_size_mb: number;
  cost_description: string;
}
