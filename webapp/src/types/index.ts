// Types pour AI Studio Pro Web App

export interface User {
  id: number;
  email: string;
  full_name?: string;
  credits: number;
  subscription_tier: 'free' | 'starter' | 'pro' | 'enterprise';
  subscription_status: string;
  is_active: boolean;
  is_admin?: boolean;
  role?: string;
  created_at: string;
}

export interface Generation {
  id: number;
  generation_type: 'image' | 'video' | 'img2img' | 'img2vid';
  prompt: string;
  negative_prompt?: string;
  status: 'queued' | 'pending' | 'processing' | 'completed' | 'failed';
  result_url?: string;
  thumbnail_url?: string;
  width?: number;
  height?: number;
  duration?: number;
  style?: string;
  credits_used: number;
  created_at: string;
  completed_at?: string;
}

export interface CreditTransaction {
  id: number;
  amount: number;
  transaction_type: 'purchase' | 'usage' | 'bonus' | 'refund' | 'subscription';
  description?: string;
  balance_after: number;
  created_at: string;
}

export interface CreditPackage {
  id: string;
  name: string;
  credits: number;
  price: number;
  currency: string;
  description?: string;
}

export interface SubscriptionPlan {
  id: string;
  name: string;
  tier: string;
  price: number;
  currency: string;
  interval: string;
  credits_per_month: number;
  features: string[];
  description?: string;
  stripe_price_id?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  full_name?: string;
}

export interface ImageGenerationRequest {
  prompt: string;
  negative_prompt?: string;
  width: number;
  height: number;
  style?: string;
  num_inference_steps?: number;
  guidance_scale?: number;
}


export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  status_code?: number;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}


export interface SupportTicket {
  id: number;
  user_id: number;
  user_email?: string | null;
  user_name?: string | null;
  subject: string;
  message: string;
  status: 'open' | 'in_progress' | 'resolved' | 'closed' | string;
  admin_notes?: string | null;
  created_at?: string;
  updated_at?: string;
}
