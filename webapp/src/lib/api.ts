import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { normalizeApiV1Base, normalizeBackendRoot } from '@/lib/url-config';

export const API_BASE_URL = normalizeApiV1Base(
  process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL
);
export const BACKEND_BASE_URL = normalizeBackendRoot(
  process.env.NEXT_PUBLIC_BACKEND_URL || API_BASE_URL
);

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const { accessToken } = useAuthStore.getState();
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const { refreshToken, setTokens, logout } = useAuthStore.getState();
        
        if (!refreshToken) {
          logout();
          return Promise.reject(error);
        }
        
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        
        const { access_token, refresh_token } = response.data;
        setTokens(access_token, refresh_token);
        
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        const { logout } = useAuthStore.getState();
        logout();
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

// API functions
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  
  register: (email: string, password: string, full_name?: string) =>
    api.post('/auth/register', { email, password, full_name }),
  
  logout: () => {
    const { refreshToken } = useAuthStore.getState();
    return api.post('/auth/logout', { refresh_token: refreshToken });
  },

  changePassword: (current_password: string, new_password: string) =>
    api.post('/auth/change-password', { current_password, new_password }),
};

export const userApi = {
  getMe: () => api.get('/users/me'),
  updateMe: (data: Partial<{ email: string; full_name: string }>) =>
    api.patch('/users/me', data),
  getStats: () => api.get('/users/me/stats'),
};

export const generationApi = {
  generateImage: (data: {
    prompt: string;
    negative_prompt?: string;
    width: number;
    height: number;
    style?: string;
  }) => api.post('/generations/images', data),

  generateImageFromReference: (
    data: FormData,
    mode?: 'auto' | 'person_identity' | 'product_ad' | 'flyer_poster' | 'background_replace' | 'creative_image'
  ) => {
    const endpointByMode: Record<string, string> = {
      auto: '/generations/image/img2img/auto',
      person_identity: '/generations/image/img2img/person-identity',
      product_ad: '/generations/image/img2img/product-ad',
      flyer_poster: '/generations/image/img2img/flyer-poster',
      background_replace: '/generations/image/img2img/background-replace',
      creative_image: '/generations/image/img2img/creative-image',
    };
    const endpoint = endpointByMode[mode || 'auto'] || '/generations/image/img2img';
    return api.post(endpoint, data, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  getGenerations: (params?: {
    generation_type?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }) => api.get('/generations/', { params }),
  
  getGeneration: (id: number) => api.get(`/generations/${id}`),
  
  deleteGeneration: (id: number) => api.delete(`/generations/${id}`),
};


export const creditsApi = {
  getBalance: () => api.get('/credits/balance'),
  getPackages: () => api.get('/credits/packages'),
  purchase: async (packageId: string) => {
    const payload = { package_id: packageId };
    try {
      return await api.post('/credits/purchase', payload);
    } catch (error: any) {
      // Compatibility for deployments that expose the older checkout alias only.
      if (error?.response?.status === 404 || error?.response?.status === 405) {
        return api.post('/credits/checkout', payload);
      }
      throw error;
    }
  },
  getHistory: (limit?: number) =>
    api.get('/credits/history', { params: { limit } }),
};

export const supportApi = {
  createTicket: (data: { subject: string; message: string }) =>
    api.post('/support/tickets', data),
  getTickets: (params?: { page?: number; page_size?: number }) =>
    api.get('/support/tickets', { params }),
};

export const subscriptionApi = {
  getPlans: () => api.get('/subscriptions/plans'),
  getCurrent: () => api.get('/subscriptions/current'),
  subscribe: (tier: string) =>
    api.post('/subscriptions/subscribe', { tier }),
  cancel: () => api.post('/subscriptions/cancel'),
};


export const runtimeApi = {
  getStatus: () => api.get('/runtime/status'),
};


// V10.14 frontend safety helper.
// Internal ComfyUI backdrop assets must not be used as user-facing preview/download.
export function isInternalV10AssetUrl(url?: string | null): boolean {
  const value = String(url || "").toLowerCase();
  return (
    (value.includes("v10_comfy_backdrop_") ||
      value.includes("aistudiopro_v10_backdrop_flyer") ||
      value.includes("source_lock_backdrop") ||
      value.includes("commercial_backdrop") ||
      value.includes("backdrop_flyer")) &&
    !value.includes("generated_v10_flyer_")
  );
}
