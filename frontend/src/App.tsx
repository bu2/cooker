import {
  ChangeEvent,
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Recipe,
  RecipeList,
  buildImageUrl,
  fetchRecipes,
  searchRecipes,
  fetchRecipeById,
  fetchLanguages,
  LanguageCode,
  DEFAULT_LANGUAGE,
} from "./api";
import "./App.css";

const DEFAULT_FLAG = "🌐";

const LANGUAGE_METADATA: Record<string, { nativeName: string; flag: string }> = {
  en: { nativeName: "English", flag: "🇺🇸" },
  "en-gb": { nativeName: "English (UK)", flag: "🇬🇧" },
  fr: { nativeName: "Français", flag: "🇫🇷" },
  es: { nativeName: "Español", flag: "🇪🇸" },
  de: { nativeName: "Deutsch", flag: "🇩🇪" },
  it: { nativeName: "Italiano", flag: "🇮🇹" },
  pt: { nativeName: "Português", flag: "🇵🇹" },
  "pt-br": { nativeName: "Português (Brasil)", flag: "🇧🇷" },
  nl: { nativeName: "Nederlands", flag: "🇳🇱" },
  sv: { nativeName: "Svenska", flag: "🇸🇪" },
  fi: { nativeName: "Suomi", flag: "🇫🇮" },
  da: { nativeName: "Dansk", flag: "🇩🇰" },
  pl: { nativeName: "Polski", flag: "🇵🇱" },
  cs: { nativeName: "Čeština", flag: "🇨🇿" },
  tr: { nativeName: "Türkçe", flag: "🇹🇷" },
  ru: { nativeName: "Русский", flag: "🇷🇺" },
  zh: { nativeName: "中文", flag: "🇨🇳" },
  "zh-hant": { nativeName: "中文（繁體）", flag: "🇹🇼" },
  ja: { nativeName: "日本語", flag: "🇯🇵" },
  ko: { nativeName: "한국어", flag: "🇰🇷" },
  ar: { nativeName: "العربية", flag: "🇸🇦" },
  hi: { nativeName: "हिन्दी", flag: "🇮🇳" },
};

const FALLBACK_LANGUAGE_NAMES: Record<string, string> = {
  en: "English",
  fr: "Français",
  es: "Español",
  de: "Deutsch",
  zh: "中文",
  "en-gb": "English (UK)",
  "pt-br": "Português (Brasil)",
  "zh-hant": "中文（繁體）",
  it: "Italiano",
  pt: "Português",
  nl: "Nederlands",
  sv: "Svenska",
  fi: "Suomi",
  da: "Dansk",
  pl: "Polski",
  cs: "Čeština",
  tr: "Türkçe",
  ru: "Русский",
  ja: "日本語",
  ko: "한국어",
  ar: "العربية",
  hi: "हिन्दी",
};

function normalizeLanguageCode(code: string): string {
  return code.toLowerCase().replace(/_/g, "-");
}

function toFlagEmoji(region: string): string | null {
  if (!/^[A-Z]{2}$/.test(region)) {
    return null;
  }
  const base = 127397;
  const chars = [...region];
  return String.fromCodePoint(
    ...chars.map((char) => base + char.charCodeAt(0))
  );
}

function resolveLanguageMetadata(
  code: string
): { nativeName: string; flag: string } | undefined {
  const normalized = normalizeLanguageCode(code);
  if (LANGUAGE_METADATA[normalized]) {
    return LANGUAGE_METADATA[normalized];
  }
  const [base] = normalized.split("-");
  return LANGUAGE_METADATA[base];
}

function getLanguageName(code: LanguageCode): string {
  const normalized = normalizeLanguageCode(code);
  const meta = resolveLanguageMetadata(normalized);
  if (meta?.nativeName) return meta.nativeName;
  const [base] = normalized.split("-");
  return (
    FALLBACK_LANGUAGE_NAMES[normalized] ||
    FALLBACK_LANGUAGE_NAMES[base] ||
    base ||
    normalized
  );
}

function getLanguageFlag(code: string): string {
  const metadata = resolveLanguageMetadata(code);
  if (metadata?.flag) {
    return metadata.flag;
  }
  const normalized = normalizeLanguageCode(code);
  const parts = normalized.split("-");
  if (parts.length > 1) {
    const region = parts[parts.length - 1].toUpperCase();
    const flag = toFlagEmoji(region);
    if (flag) {
      return flag;
    }
  }
  return DEFAULT_FLAG;
}

function truncate(text: string, length = 160): string {
  if (text.length <= length) return text;
  return `${text.slice(0, length)}…`;
}

const PLACEHOLDER_COLORS = ["#f97316", "#2dd4bf", "#38bdf8", "#a855f7", "#facc15"];

function renderInline(text: string): ReactNode[] {
  const segments: ReactNode[] = [];
  const pattern = /(`([^`]+)`)|(\*\*([^*]+)\*\*)|(__([^_]+)__)|(\*([^*]+)\*)|(_([^_]+)_)|(\[([^\]]+)\]\(([^)]+)\))/g;
  let lastIndex = 0;
  let key = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push(text.slice(lastIndex, match.index));
    }

    if (match[1]) {
      segments.push(
        <code key={`inline-code-${key++}`} className="markdown__inline-code">
          {match[2]}
        </code>
      );
    } else if (match[3]) {
      segments.push(
        <strong key={`bold-${key++}`}>{match[4]}</strong>
      );
    } else if (match[5]) {
      segments.push(
        <strong key={`bold-${key++}`}>{match[6]}</strong>
      );
    } else if (match[7]) {
      segments.push(
        <em key={`italic-${key++}`}>{match[8]}</em>
      );
    } else if (match[9]) {
      segments.push(
        <em key={`italic-${key++}`}>{match[10]}</em>
      );
    } else if (match[11]) {
      const label = match[12];
      const href = match[13];
      const isSafeLink = /^https?:\/\//i.test(href);
      if (isSafeLink) {
        segments.push(
          <a key={`link-${key++}`} href={href} target="_blank" rel="noreferrer">
            {label}
          </a>
        );
      } else {
        segments.push(label);
      }
    }

    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    segments.push(text.slice(lastIndex));
  }

  return segments.length > 0 ? segments : [text];
}

// (duplicate removed)

function buildRecipePageUrl(id: string, lang: LanguageCode): string {
  try {
    const url = new URL(window.location.href);
    url.searchParams.set("lang", normalizeLanguageCode(lang));
    url.searchParams.set("id", id);
    // Keep permalinks clean: drop transient search query
    url.searchParams.delete("q");
    return url.toString();
  } catch {
    return `/?lang=${encodeURIComponent(normalizeLanguageCode(lang))}&id=${encodeURIComponent(id)}`;
  }
}

function headingElement(level: number, key: string, children: ReactNode) {
  switch (level) {
    case 1:
      return (
        <h1 key={key} className="markdown__heading markdown__heading--h1">
          {children}
        </h1>
      );
    case 2:
      return (
        <h2 key={key} className="markdown__heading markdown__heading--h2">
          {children}
        </h2>
      );
    case 3:
      return (
        <h3 key={key} className="markdown__heading markdown__heading--h3">
          {children}
        </h3>
      );
    case 4:
      return (
        <h4 key={key} className="markdown__heading markdown__heading--h4">
          {children}
        </h4>
      );
    case 5:
      return (
        <h5 key={key} className="markdown__heading markdown__heading--h5">
          {children}
        </h5>
      );
    default:
      return (
        <h6 key={key} className="markdown__heading markdown__heading--h6">
          {children}
        </h6>
      );
  }
}

function parseMarkdown(markdown: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listType: "ul" | "ol" | null = null;
  let codeBlock: string[] | null = null;
  let blockKey = 0;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const text = paragraph.join("\n").trim();
    if (text) {
      nodes.push(
        <p key={`paragraph-${blockKey++}`} className="markdown__paragraph">
          {renderInline(text)}
        </p>
      );
    }
    paragraph = [];
  };

  const flushList = () => {
    if (!listItems.length || !listType) return;
    const keyBase = blockKey++;
    const items = listItems.map((item, index) => (
      <li key={`list-${keyBase}-item-${index}`}>{renderInline(item)}</li>
    ));
    nodes.push(
      listType === "ul" ? (
        <ul key={`list-${keyBase}`} className="markdown__list">
          {items}
        </ul>
      ) : (
        <ol key={`list-${keyBase}`} className="markdown__list markdown__list--ordered">
          {items}
        </ol>
      )
    );
    listItems = [];
    listType = null;
  };

  const flushCode = () => {
    if (!codeBlock) return;
    nodes.push(
      <pre key={`code-${blockKey++}`} className="markdown__code-block">
        <code>{codeBlock.join("\n").replace(/\n$/, "")}</code>
      </pre>
    );
    codeBlock = null;
  };

  for (const rawLine of lines) {
    const trimmedLine = rawLine.replace(/\s+$/g, "");

    if (codeBlock) {
      if (/^```/.test(trimmedLine)) {
        flushCode();
      } else {
        codeBlock.push(rawLine);
      }
      continue;
    }

    if (/^```/.test(trimmedLine)) {
      flushParagraph();
      flushList();
      codeBlock = [];
      continue;
    }

    if (!trimmedLine.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = trimmedLine.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = headingMatch[1].length;
      const text = headingMatch[2].trim();
      nodes.push(headingElement(Math.min(level, 6), `heading-${blockKey++}`, renderInline(text)));
      continue;
    }

    const blockquoteMatch = trimmedLine.match(/^>\s?(.*)$/);
    if (blockquoteMatch) {
      flushParagraph();
      flushList();
      nodes.push(
        <blockquote key={`blockquote-${blockKey++}`} className="markdown__blockquote">
          {renderInline(blockquoteMatch[1].trim())}
        </blockquote>
      );
      continue;
    }

    const unorderedMatch = trimmedLine.match(/^[-*+]\s+(.*)$/);
    if (unorderedMatch) {
      flushParagraph();
      if (listType && listType !== "ul") {
        flushList();
      }
      listType = "ul";
      listItems.push(unorderedMatch[1].trim());
      continue;
    }

    const orderedMatch = trimmedLine.match(/^(\d+)[.)]\s+(.*)$/);
    if (orderedMatch) {
      flushParagraph();
      if (listType && listType !== "ol") {
        flushList();
      }
      listType = "ol";
      listItems.push(orderedMatch[2].trim());
      continue;
    }

    paragraph.push(trimmedLine);
  }

  if (codeBlock) {
    flushCode();
  }
  flushParagraph();
  flushList();

  return nodes.length ? nodes : [
    <p key="paragraph-0" className="markdown__paragraph">
      {renderInline(markdown)}
    </p>
  ];
}

function MarkdownContent({ text }: { text: string }) {
  const nodes = useMemo(() => parseMarkdown(text), [text]);
  return <div className="modal__markdown">{nodes}</div>;
}

function RecipeCard({
  recipe,
  onSelect,
  isMobile,
}: {
  recipe: Recipe;
  onSelect: (id: string) => void;
  isMobile: boolean;
}) {
  const imageUrl = buildImageUrl(recipe.image_url);
  const fallbackColor = useMemo(
    () => PLACEHOLDER_COLORS[recipe.id.charCodeAt(0) % PLACEHOLDER_COLORS.length],
    [recipe.id]
  );

  const handleClick = () => {
    if (isMobile) {
      const lang = (recipe.language as LanguageCode) || DEFAULT_LANGUAGE;
      const href = buildRecipePageUrl(recipe.id, lang);
      window.open(href, "_blank", "noopener,noreferrer");
      return;
    }
    onSelect(recipe.id);
  };

  return (
    <article className="card" onClick={handleClick}>
      {imageUrl ? (
        <img src={imageUrl} alt={recipe.title ?? recipe.id} loading="lazy" />
      ) : (
        <div className="card__placeholder" style={{ background: fallbackColor }}>
          <span>{(recipe.title || recipe.id).slice(0, 2).toUpperCase()}</span>
        </div>
      )}
      <div className="card__body">
        <h3>{recipe.title || recipe.id}</h3>
        <p>{truncate(recipe.description ?? recipe.text)}</p>
        {recipe.n_tokens != null && (
          <span className="card__meta">Tokens: {recipe.n_tokens.toLocaleString()}</span>
        )}
      </div>
    </article>
  );
}

function RecipeModal({ recipe, onClose }: { recipe: Recipe; onClose: () => void }) {
  const imageUrl = buildImageUrl(recipe.image_url);
  return (
    <div className="modal__backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div>
        <a
            className="modal__open"
            href={buildRecipePageUrl(
              recipe.id,
              (recipe.language as LanguageCode) || DEFAULT_LANGUAGE
            )}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open recipe in a new tab"
          >
            Open in new tab ↗
        </a>
        <button className="modal__close" onClick={onClose}>
          ×
        </button>
        </div>
        <header className="modal__header">
          <div className="modal__header-info">
            <h2 className="modal__title">{recipe.title || recipe.id}</h2>
            {recipe.n_tokens != null && (
              <p className="modal__tokens">Tokens: {recipe.n_tokens.toLocaleString()}</p>
            )}
          </div>
        </header>
        {imageUrl && (
          <img src={imageUrl} alt={recipe.title ?? recipe.id} className="modal__image" />
        )}
        <MarkdownContent text={recipe.text} />
      </div>
    </div>
  );
}

function App() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [query, setQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Recipe | null>(null);
  const [isStandalone, setIsStandalone] = useState<boolean>(false);
  const [language, setLanguage] = useState<LanguageCode>(DEFAULT_LANGUAGE);
  const [availableLanguages, setAvailableLanguages] = useState<LanguageCode[]>([DEFAULT_LANGUAGE]);
  const [activeQuery, setActiveQuery] = useState<string | null>(null);
  const activeQueryRef = useRef<string | null>(null);
  const bootstrappedRef = useRef(false);
  const [isMobile, setIsMobile] = useState<boolean>(false);

  const setURLParams = useCallback(
    (lang: LanguageCode, q: string | null | undefined, id?: string | null) => {
      try {
        const url = new URL(window.location.href);
        if (lang) {
          url.searchParams.set("lang", normalizeLanguageCode(lang));
        }
        if (q && q.trim()) {
          url.searchParams.set("q", q.trim());
        } else {
          url.searchParams.delete("q");
        }
        if (id && id.trim()) {
          url.searchParams.set("id", id);
        } else {
          url.searchParams.delete("id");
        }
        const next = url.toString();
        if (next !== window.location.href) {
          window.history.replaceState({}, "", next);
        }
      } catch {
        // no-op for non-browser envs
      }
    },
    []
  );

  const formatLanguage = useCallback(
    (code: LanguageCode) => {
      const flag = getLanguageFlag(code);
      const base = normalizeLanguageCode(code).split("-")[0];
      const label = isMobile ? base : getLanguageName(code);
      return `${flag} ${label}`;
    },
    [isMobile]
  );

  // Track mobile viewport to adjust language selector labeling
  useEffect(() => {
    if (typeof window === "undefined" || !("matchMedia" in window)) return;
    const mql = window.matchMedia("(max-width: 600px)");
    const update = () => setIsMobile(mql.matches);
    update();
    // Older Safari uses addListener/removeListener
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", update);
      return () => mql.removeEventListener("change", update);
    } else if (typeof mql.addListener === "function") {
      mql.addListener(update);
      return () => mql.removeListener(update);
    }
  }, []);

  useEffect(() => {
    activeQueryRef.current = activeQuery;
  }, [activeQuery]);

  const loadRecipesForLanguage = useCallback(async (lang: LanguageCode) => {
    setLoading(true);
    setError(null);
    try {
      const data: RecipeList = await fetchRecipes(24, 0, lang);
      setRecipes(data.items);
      setTotal(data.total);
      setActiveQuery(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load recipes";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const performSearch = useCallback(async (term: string, lang: LanguageCode) => {
    setLoading(true);
    setError(null);
    try {
      const items = await searchRecipes(term, 60, lang);
      setRecipes(items);
      setTotal(items.length);
      setActiveQuery(term);
      setURLParams(lang, term, null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Search failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [setURLParams]);

  const applyLanguageChange = useCallback(
    async (nextLanguage: LanguageCode) => {
      setLanguage(nextLanguage);
      setError(null);

      const keepRecipe = isStandalone && selected?.id;
      if (keepRecipe) {
        try {
          setLoading(true);
          const updated = await fetchRecipeById(selected!.id, nextLanguage);
          setSelected(updated);
          setURLParams(nextLanguage, activeQueryRef.current, selected!.id);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to load recipe";
          setError(message);
        } finally {
          setLoading(false);
        }
        return;
      }

      setSelected(null);
      const active = activeQueryRef.current;
      if (active && active.trim()) {
        await performSearch(active, nextLanguage);
      } else {
        await loadRecipesForLanguage(nextLanguage);
      }
      setURLParams(nextLanguage, activeQueryRef.current, null);
    },
    [isStandalone, selected, loadRecipesForLanguage, performSearch, setURLParams]
  );

  useEffect(() => {
    if (bootstrappedRef.current) return;
    bootstrappedRef.current = true;

    const url = new URL(window.location.href);
    const urlLang = (url.searchParams.get("lang") || DEFAULT_LANGUAGE) as LanguageCode;
    const urlQueryRaw = url.searchParams.get("q") || "";
    const urlId = url.searchParams.get("id") || "";
    const urlQuery = urlQueryRaw.trim();

    setLanguage(urlLang);
    setQuery(urlQueryRaw);
    setIsStandalone(Boolean(urlId));

    const run = async () => {
      if (urlQuery) {
        await performSearch(urlQuery, urlLang);
      } else {
        await loadRecipesForLanguage(urlLang);
        // Preserve id if present on initial load
        if (!urlId) {
          setURLParams(urlLang, null, null);
        }
      }
      if (urlId) {
        try {
          setLoading(true);
          const initial = await fetchRecipeById(urlId, urlLang);
          setSelected(initial);
        } catch (err) {
          const message = err instanceof Error ? err.message : "Failed to load recipe";
          setError(message);
        } finally {
          setLoading(false);
        }
      }
    };

    void run();
  }, [loadRecipesForLanguage, performSearch, setURLParams]);

  useEffect(() => {
    let cancelled = false;

    const loadLanguages = async () => {
      try {
        const langs = await fetchLanguages();
        if (cancelled || !langs.length) {
          return;
        }
        setAvailableLanguages(langs);
        if (!langs.includes(language)) {
          const nextLanguage = langs[0];
          if (nextLanguage) {
            await applyLanguageChange(nextLanguage);
          }
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        const message = err instanceof Error ? err.message : "Failed to load languages";
        setError(message);
      }
    };

    void loadLanguages();

    return () => {
      cancelled = true;
    };
  }, [applyLanguageChange, language]);

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      await loadRecipesForLanguage(language);
      return;
    }
    await performSearch(trimmed, language);
  };

  const handleSelect = async (id: string) => {
    try {
      const recipe = await fetchRecipeById(id, language);
      setSelected(recipe);
      setURLParams(language, activeQueryRef.current, id);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load recipe";
      setError(message);
    }
  };

  const handleLanguageChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextLanguage = event.target.value as LanguageCode;
    if (nextLanguage === language) {
      return;
    }
    void applyLanguageChange(nextLanguage);
  };

  

  const clearSelection = () => {
    setSelected(null);
    setIsStandalone(false);
    setURLParams(language, activeQueryRef.current, null);
  };

  useEffect(() => {
    if (!selected || isStandalone) {
      return;
    }
    const { style } = document.body;
    const previousOverflow = style.overflow;
    style.overflow = "hidden";
    return () => {
      style.overflow = previousOverflow;
    };
  }, [selected, isStandalone]);

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__header-top">
          <div>
            <h1>La Tambouille</h1>
            <p className="app__subtitle">
              La cuisine française traditionnelle dans votre assiette.
            </p>
          </div>
          <div className="app__actions">
            {!isStandalone && (
              <form className="search" onSubmit={handleSearch}>
                <input
                  type="search"
                  placeholder="Rechercher..."
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  aria-label="Search recipes"
                />
              </form>
            )}
            <div className="language-switcher">
              <select
                id="language-select"
                value={language}
                onChange={handleLanguageChange}
                disabled={availableLanguages.length <= 1}
              >
                {availableLanguages.map((code) => (
                  <option key={code} value={code}>
                    {formatLanguage(code)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </header>

      {error && <div className="alert alert--error">{error}</div>}
      {loading && <div className="alert">Loading…</div>}

      {!isStandalone && (
        <div className="stats">
          <span>{total.toLocaleString()} recipes</span>
          {activeQuery && <span>Matching “{activeQuery}”</span>}
        </div>
      )}

      {isStandalone ? (
        <section className="recipe-view">
          {loading && <div className="alert">Loading…</div>}
          {selected && (
            <>
              <header className="modal__header">
                <div className="modal__header-info">
                  <h2 className="modal__title">{selected.title || selected.id}</h2>
                  {selected.n_tokens != null && (
                    <p className="modal__tokens">Tokens: {selected.n_tokens.toLocaleString()}</p>
                  )}
                </div>
              </header>
              {buildImageUrl(selected.image_url) && (
                <img
                  src={buildImageUrl(selected.image_url)}
                  alt={selected.title ?? selected.id}
                  className="modal__image"
                />
              )}
              <MarkdownContent text={selected.text} />
            </>
          )}
        </section>
      ) : (
        <>
          <section className="grid">
            {recipes.map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} onSelect={handleSelect} isMobile={isMobile} />
            ))}
          </section>
          {selected && <RecipeModal recipe={selected} onClose={clearSelection} />}
        </>
      )}
    </div>
  );
}

export default App;
