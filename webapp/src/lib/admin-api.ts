import { api } from "@/lib/api";

export type Paginated<T> = {
  items: T[];
  total?: number;
  page?: number;
  page_size?: number;
};

export type AdminUser = {
  id: number;
  email: string;
  full_name?: string | null;
  credits?: number;
  is_admin?: boolean;
  is_active?: boolean;
  created_at?: string;
  last_login_at?: string | null;
};

export type AdminGeneration = {
  id: number;
  user_id?: number;
  user_email?: string;
  generation_type: "image" | "video" | "img2img" | "img2vid" | string;
  prompt: string;
  status: string;
  width?: number;
  height?: number;
  duration?: number | null;
  credits_used?: number;
  result_url?: string | null;
  created_at?: string;
};

export type AdminTicket = {
  id: number;
  user_id?: number;
  user_email?: string;
  subject: string;
  message: string;
  status: "open" | "in_progress" | "resolved" | "closed" | string;
  created_at?: string;
  updated_at?: string;
  admin_notes?: string | null;
  user_name?: string | null;
};

export type AdminOverview = {
  total_users: number;
  active_users?: number;
  admin_users?: number;
  total_credits?: number;
  total_generations: number;
  completed_generations?: number;
  failed_generations?: number;
  image_generations?: number;
  video_generations?: number;
  total_revenue: number;
  open_tickets?: number;
};

export type SeriesPoint = { day: string; count: number };
export type TopModel = { model: string; count: number; avg_time: number };

function normalizeList<T>(data: any): Paginated<T> {
  if (!data) return { items: [] as T[] };

  // backend might return {items, total}
  if (Array.isArray(data.items)) return data as Paginated<T>;

  // backend might return {data: {items}}
  if (data.data && Array.isArray(data.data.items)) return data.data as Paginated<T>;

  // or return plain array
  if (Array.isArray(data)) return { items: data as T[] };

  // or {users: []}
  const maybe = Object.values(data).find((v) => Array.isArray(v));
  if (Array.isArray(maybe)) return { items: maybe as T[] };

  return { items: [] as T[] };
}

export const adminApi = {
  // --- Stats (already used by your project) ---
  async overview(): Promise<AdminOverview> {
    const r = await api.get("/admin/stats/overview");
    return r.data;
  },

  async generationsPerDay(days = 30): Promise<SeriesPoint[]> {
    const r = await api.get(`/admin/stats/generations_per_day?days=${days}`);
    return r.data?.data ?? r.data ?? [];
  },

  async topModels(days = 30): Promise<TopModel[]> {
    const r = await api.get(`/admin/stats/top_models?days=${days}`);
    return r.data?.data ?? r.data ?? [];
  },

  // --- Users ---
  async listUsers(params?: { q?: string; page?: number; page_size?: number }): Promise<Paginated<AdminUser>> {
    const r = await api.get("/admin/users", { params });
    return normalizeList<AdminUser>(r.data);
  },

  async patchUser(id: number, body: { is_admin?: boolean; is_active?: boolean; credits?: number }): Promise<AdminUser> {
    const r = await api.patch(`/admin/users/${id}`, body);
    return r.data;
  },

  async deleteUser(id: number): Promise<void> {
    await api.delete(`/admin/users/${id}`);
  },

  // --- Generations moderation ---
  async listGenerations(params?: {
    q?: string;
    type?: "image" | "video" | "img2img" | "img2vid";
    status?: string;
    page?: number;
    page_size?: number;
  }): Promise<Paginated<AdminGeneration>> {
    const r = await api.get("/admin/generations", { params });
    return normalizeList<AdminGeneration>(r.data);
  },

  async deleteGeneration(id: number): Promise<void> {
    await api.delete(`/admin/generations/${id}`);
  },

  // --- Tickets / Reclamations (optional) ---
  async listTickets(params?: { q?: string; status?: string; page?: number; page_size?: number }): Promise<Paginated<AdminTicket>> {
    const r = await api.get("/admin/support/tickets", { params });
    return normalizeList<AdminTicket>(r.data);
  },

  async patchTicket(id: number, body: { status?: string; admin_notes?: string }): Promise<AdminTicket> {
    const r = await api.patch(`/admin/support/tickets/${id}`, body);
    return r.data;
  },

  async deleteTicket(id: number): Promise<void> {
    await api.delete(`/admin/support/tickets/${id}`);
  },
};
