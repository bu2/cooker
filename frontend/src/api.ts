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

function getBaseUrl(): string {
  const fromEnv = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (fromEnv) {
    return fromEnv.replace(/\/$/, "");
  }
  // In dev, rely on Vite proxy (see vite.config.ts)
  if (import.meta.env.DEV) {
    return "/api";
  }
  // In production, default to same-origin (behind a reverse proxy)
  return "";
}

const API_BASE = getBaseUrl();

// Simple in-memory cache for languages to avoid redundant network calls
let __languagesCache: LanguageCode[] | null = null;
let __languagesPromise: Promise<LanguageCode[]> | null = null;

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
  if (__languagesCache) {
    return __languagesCache;
  }
  if (__languagesPromise) {
    return __languagesPromise;
  }
  __languagesPromise = (async () => {
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
  })()
    .then((result) => {
      __languagesCache = result;
      __languagesPromise = null;
      return result;
    })
    .catch((err) => {
      __languagesPromise = null;
      throw err;
    });
  return __languagesPromise;
}
