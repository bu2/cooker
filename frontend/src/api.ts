export type LanguageCode = string;

export const DEFAULT_LANGUAGE: LanguageCode = "fr";

export interface Recipe {
  id: string;
  title?: string | null;
  description?: string | null;
  text: string;
  n_tokens?: number | null;
  image_url?: string | null;
  language?: LanguageCode;
}

export interface RecipeList {
  total: number;
  items: Recipe[];
}

interface LanguageListResponse {
  languages: string[];
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

export async function fetchRecipes(
  limit = 24,
  offset = 0,
  language: LanguageCode = DEFAULT_LANGUAGE
): Promise<RecipeList> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    lang: language,
  });
  const resp = await fetch(`${API_BASE}/recipes?${params.toString()}`);
  return handleResponse<RecipeList>(resp);
}

export async function searchRecipes(
  query: string,
  limit = 24,
  language: LanguageCode = DEFAULT_LANGUAGE
): Promise<Recipe[]> {
  const params = new URLSearchParams({ q: query, limit: String(limit), lang: language });
  const resp = await fetch(`${API_BASE}/search?${params.toString()}`);
  return handleResponse<Recipe[]>(resp);
}

export async function fetchRecipeById(
  id: string,
  language: LanguageCode = DEFAULT_LANGUAGE
): Promise<Recipe> {
  const params = new URLSearchParams({ lang: language });
  const resp = await fetch(`${API_BASE}/recipes/${encodeURIComponent(id)}?${params.toString()}`);
  return handleResponse<Recipe>(resp);
}

export async function fetchLanguages(): Promise<LanguageCode[]> {
  const resp = await fetch(`${API_BASE}/languages`);
  const data = await handleResponse<LanguageListResponse>(resp);
  if (!data.languages || data.languages.length === 0) {
    return [DEFAULT_LANGUAGE];
  }
  const seen = new Set<string>();
  const normalized = data.languages
    .map((code) => code.trim())
    .filter((code) => {
      if (!code) return false;
      const lower = code.toLowerCase();
      if (seen.has(lower)) return false;
      seen.add(lower);
      return true;
    });
  return normalized.length ? normalized : [DEFAULT_LANGUAGE];
}
