import {
  ChangeEvent,
  FormEvent,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
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

const FALLBACK_LANGUAGE_NAMES: Record<string, string> = {
  en: "English",
  fr: "Français",
  es: "Español",
  de: "Deutsch",
  zh: "中文",
};

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

function RecipeCard({ recipe, onSelect }: { recipe: Recipe; onSelect: (id: string) => void }) {
  const imageUrl = buildImageUrl(recipe.image_url);
  const fallbackColor = useMemo(
    () => PLACEHOLDER_COLORS[recipe.id.charCodeAt(0) % PLACEHOLDER_COLORS.length],
    [recipe.id]
  );

  return (
    <article className="card" onClick={() => onSelect(recipe.id)}>
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
        <button className="modal__close" onClick={onClose}>
          ×
        </button>
        <header>
          <h2>{recipe.title || recipe.id}</h2>
          {recipe.n_tokens != null && (
            <p className="modal__tokens">Tokens: {recipe.n_tokens.toLocaleString()}</p>
          )}
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
  const [language, setLanguage] = useState<LanguageCode>(DEFAULT_LANGUAGE);
  const [availableLanguages, setAvailableLanguages] = useState<LanguageCode[]>([DEFAULT_LANGUAGE]);

  const languageDisplayNames = useMemo(() => {
    try {
      return new Intl.DisplayNames([navigator.language || "en"], { type: "language" });
    } catch (err) {
      return null;
    }
  }, []);

  const formatLanguage = useCallback(
    (code: LanguageCode) => {
      if (languageDisplayNames) {
        const display = languageDisplayNames.of(code);
        if (display) {
          return display;
        }
      }
      const fallback = FALLBACK_LANGUAGE_NAMES[code.toLowerCase()];
      return fallback ?? code;
    },
    [languageDisplayNames]
  );

  const loadInitial = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: RecipeList = await fetchRecipes(24, 0, language);
      setRecipes(data.items);
      setTotal(data.total);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load recipes";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => {
    loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    let cancelled = false;

    const loadLanguages = async () => {
      try {
        const langs = await fetchLanguages();
        if (cancelled || !langs.length) {
          return;
        }
        setAvailableLanguages(langs);
        let changed = false;
        setLanguage((current) => {
          if (langs.includes(current)) {
            return current;
          }
          changed = true;
          return langs[0];
        });
        if (changed) {
          setQuery("");
          setSelected(null);
          setError(null);
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        const message = err instanceof Error ? err.message : "Failed to load languages";
        setError(message);
      }
    };

    loadLanguages();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    const trimmed = query.trim();
    if (!trimmed) {
      return loadInitial();
    }
    setLoading(true);
    try {
      const items = await searchRecipes(trimmed, 60, language);
      setRecipes(items);
      setTotal(items.length);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Search failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = async (id: string) => {
    try {
      const recipe = await fetchRecipeById(id, language);
      setSelected(recipe);
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
    setLanguage(nextLanguage);
    setQuery("");
    setSelected(null);
    setError(null);
  };

  const handleReset = () => {
    setQuery("");
    loadInitial();
  };

  const clearSelection = () => setSelected(null);

  useEffect(() => {
    if (!selected) {
      return;
    }
    const { style } = document.body;
    const previousOverflow = style.overflow;
    style.overflow = "hidden";
    return () => {
      style.overflow = previousOverflow;
    };
  }, [selected]);

  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1>Recipe Gallery</h1>
          <p className="app__subtitle">
            Browse AI-generated recipes, search with full-text, and preview the dishes.
          </p>
        </div>
        <div className="app__actions">
          <div className="language-switcher">
            <label htmlFor="language-select">Language</label>
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
          <form className="search" onSubmit={handleSearch}>
            <input
              type="search"
              placeholder="Search for ingredients, cuisines, …"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              aria-label="Search recipes"
            />
            <button type="submit">Search</button>
            <button type="button" className="search__reset" onClick={handleReset}>
              Reset
            </button>
          </form>
        </div>
      </header>

      {error && <div className="alert alert--error">{error}</div>}
      {loading && <div className="alert">Loading…</div>}

      <div className="stats">
        <span>{total.toLocaleString()} recipes</span>
        <span>Language: {formatLanguage(language)}</span>
        {query.trim() && <span>Matching “{query.trim()}”</span>}
      </div>

      <section className="grid">
        {recipes.map((recipe) => (
          <RecipeCard key={recipe.id} recipe={recipe} onSelect={handleSelect} />
        ))}
      </section>

      {selected && <RecipeModal recipe={selected} onClose={clearSelection} />}
    </div>
  );
}

export default App;
