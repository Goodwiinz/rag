// Authentication Types
export interface User {
  id: string;
  email: string;
  name: string;
  organization_id: string;
  role: 'admin' | 'user' | 'viewer';
  storage_quota_used: number; // bytes
  storage_quota_limit: number; // bytes
  created_at: string;
  last_login: string;
}

export interface Organization {
  id: string;
  name: string;
  plan: 'free' | 'pro' | 'enterprise';
  storage_limit: number;
  member_count: number;
  created_at: string;
  settings?: Record<string, any>;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  pendingEmailConfirmation: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  organization_name?: string;
  organization_id?: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export type LoginResponse = AuthResponse;

export interface RefreshResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}
