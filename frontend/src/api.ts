export interface Recipe {
  id: string;
  title?: string | null;
  text: string;
  n_tokens?: number | null;
  image_url?: string | null;
}

export interface RecipeList {
  total: number;
  items: Recipe[];
}

const DEFAULT_BASE = "http://192.168.1.13:8000";

function getBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (!fromEnv) {
    return DEFAULT_BASE;
  }
  return fromEnv.replace(/\/$/, "");
}

const API_BASE = getBaseUrl();

async function handleResponse<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const msg = await resp.text();
    throw new Error(msg || resp.statusText);
  }
  return resp.json() as Promise<T>;
}

export function buildImageUrl(imageUrl?: string | null): string | undefined {
  if (!imageUrl) return undefined;
  if (imageUrl.startsWith("http")) {
    return imageUrl;
  }
  return `${API_BASE}${imageUrl}`;
}

export async function fetchRecipes(limit = 24, offset = 0): Promise<RecipeList> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const resp = await fetch(`${API_BASE}/recipes?${params.toString()}`);
  return handleResponse<RecipeList>(resp);
}

export async function searchRecipes(query: string, limit = 24): Promise<Recipe[]> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  const resp = await fetch(`${API_BASE}/search?${params.toString()}`);
  return handleResponse<Recipe[]>(resp);
}

export async function fetchRecipeById(id: string): Promise<Recipe> {
  const resp = await fetch(`${API_BASE}/recipes/${encodeURIComponent(id)}`);
  return handleResponse<Recipe>(resp);
}
