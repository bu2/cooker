import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Recipe,
  RecipeList,
  buildImageUrl,
  fetchRecipes,
  searchRecipes,
  fetchRecipeById,
} from "./api";
import "./App.css";

function truncate(text: string, length = 160): string {
  if (text.length <= length) return text;
  return `${text.slice(0, length)}…`;
}

const PLACEHOLDER_COLORS = ["#f97316", "#2dd4bf", "#38bdf8", "#a855f7", "#facc15"];

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
        <p>{truncate(recipe.text)}</p>
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
          {recipe.n_tokens != null && <p className="modal__tokens">Tokens: {recipe.n_tokens.toLocaleString()}</p>}
        </header>
        {imageUrl && (
          <img src={imageUrl} alt={recipe.title ?? recipe.id} className="modal__image" />
        )}
        <pre className="modal__text">{recipe.text}</pre>
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

  const loadInitial = async () => {
    setLoading(true);
    setError(null);
    try {
      const data: RecipeList = await fetchRecipes();
      setRecipes(data.items);
      setTotal(data.total);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load recipes";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitial();
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
      const items = await searchRecipes(trimmed, 60);
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
      const recipe = await fetchRecipeById(id);
      setSelected(recipe);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load recipe";
      setError(message);
    }
  };

  const clearSelection = () => setSelected(null);

  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1>Recipe Gallery</h1>
          <p className="app__subtitle">
            Browse AI-generated recipes, search with full-text, and preview the dishes.
          </p>
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
          <button type="button" className="search__reset" onClick={loadInitial}>
            Reset
          </button>
        </form>
      </header>

      {error && <div className="alert alert--error">{error}</div>}
      {loading && <div className="alert">Loading…</div>}

      <div className="stats">
        <span>{total.toLocaleString()} recipes</span>
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
