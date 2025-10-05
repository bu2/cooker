import { DEFAULT_LANGUAGE, LanguageCode } from "./api";

export type I18nKey =
  | "app_subtitle"
  | "search_placeholder"
  | "open_in_new_tab"
  | "open_recipe_in_new_tab"
  | "loading"
  | "tokens_label"
  | "aria_search_recipes"
  | "error_failed_load_recipes"
  | "error_search_failed"
  | "error_failed_load_recipe"
  | "error_failed_load_languages";

function normalizeLanguageCode(code: string): string {
  return code.toLowerCase().replace(/_/g, "-");
}

type Dict = Record<I18nKey, string>;

// Translations for all languages listed in LANGUAGE_METADATA
const translations: Record<string, Partial<Dict>> = {
  // Defaults (French)
  fr: {
    app_subtitle: "La cuisine française traditionnelle dans votre assiette.",
    search_placeholder: "Rechercher…",
    open_in_new_tab: "Ouvrir dans un nouvel onglet ↗",
    open_recipe_in_new_tab: "Ouvrir la recette dans un nouvel onglet",
    loading: "Chargement…",
    tokens_label: "Jetons",
    aria_search_recipes: "Rechercher des recettes",
    error_failed_load_recipes: "Impossible de charger les recettes",
    error_search_failed: "La recherche a échoué",
    error_failed_load_recipe: "Impossible de charger la recette",
    error_failed_load_languages: "Impossible de charger les langues",
  },

  en: {
    app_subtitle: "Traditional French cuisine on your plate.",
    search_placeholder: "Search…",
    open_in_new_tab: "Open in new tab ↗",
    open_recipe_in_new_tab: "Open recipe in a new tab",
    loading: "Loading…",
    tokens_label: "Tokens",
    aria_search_recipes: "Search recipes",
    error_failed_load_recipes: "Failed to load recipes",
    error_search_failed: "Search failed",
    error_failed_load_recipe: "Failed to load recipe",
    error_failed_load_languages: "Failed to load languages",
  },

  "en-gb": {
    app_subtitle: "Traditional French cuisine on your plate.",
    search_placeholder: "Search…",
    open_in_new_tab: "Open in new tab ↗",
    open_recipe_in_new_tab: "Open recipe in a new tab",
    loading: "Loading…",
    tokens_label: "Tokens",
    aria_search_recipes: "Search recipes",
    error_failed_load_recipes: "Failed to load recipes",
    error_search_failed: "Search failed",
    error_failed_load_recipe: "Failed to load recipe",
    error_failed_load_languages: "Failed to load languages",
  },

  es: {
    app_subtitle: "La cocina francesa tradicional en tu plato.",
    search_placeholder: "Buscar…",
    open_in_new_tab: "Abrir en una nueva pestaña ↗",
    open_recipe_in_new_tab: "Abrir la receta en una nueva pestaña",
    loading: "Cargando…",
    tokens_label: "Tokens",
    aria_search_recipes: "Buscar recetas",
    error_failed_load_recipes: "No se pudieron cargar las recetas",
    error_search_failed: "La búsqueda falló",
    error_failed_load_recipe: "No se pudo cargar la receta",
    error_failed_load_languages: "No se pudieron cargar los idiomas",
  },

  de: {
    app_subtitle: "Traditionelle französische Küche auf deinem Teller.",
    search_placeholder: "Suchen…",
    open_in_new_tab: "In neuem Tab öffnen ↗",
    open_recipe_in_new_tab: "Rezept in neuem Tab öffnen",
    loading: "Laden…",
    tokens_label: "Tokens",
    aria_search_recipes: "Rezepte suchen",
    error_failed_load_recipes: "Rezepte konnten nicht geladen werden",
    error_search_failed: "Suche fehlgeschlagen",
    error_failed_load_recipe: "Rezept konnte nicht geladen werden",
    error_failed_load_languages: "Sprachen konnten nicht geladen werden",
  },

  it: {
    app_subtitle: "La cucina francese tradizionale nel tuo piatto.",
    search_placeholder: "Cerca…",
    open_in_new_tab: "Apri in una nuova scheda ↗",
    open_recipe_in_new_tab: "Apri la ricetta in una nuova scheda",
    loading: "Caricamento…",
    tokens_label: "Token",
    aria_search_recipes: "Cerca ricette",
    error_failed_load_recipes: "Impossibile caricare le ricette",
    error_search_failed: "Ricerca non riuscita",
    error_failed_load_recipe: "Impossibile caricare la ricetta",
    error_failed_load_languages: "Impossibile caricare le lingue",
  },

  pt: {
    app_subtitle: "A cozinha francesa tradicional no seu prato.",
    search_placeholder: "Pesquisar…",
    open_in_new_tab: "Abrir num novo separador ↗",
    open_recipe_in_new_tab: "Abrir a receita num novo separador",
    loading: "A carregar…",
    tokens_label: "Tokens",
    aria_search_recipes: "Pesquisar receitas",
    error_failed_load_recipes: "Falha ao carregar as receitas",
    error_search_failed: "Falha na pesquisa",
    error_failed_load_recipe: "Falha ao carregar a receita",
    error_failed_load_languages: "Falha ao carregar os idiomas",
  },

  "pt-br": {
    app_subtitle: "A culinária francesa tradicional no seu prato.",
    search_placeholder: "Pesquisar…",
    open_in_new_tab: "Abrir em nova aba ↗",
    open_recipe_in_new_tab: "Abrir a receita em uma nova aba",
    loading: "Carregando…",
    tokens_label: "Tokens",
    aria_search_recipes: "Pesquisar receitas",
    error_failed_load_recipes: "Falha ao carregar as receitas",
    error_search_failed: "Falha na pesquisa",
    error_failed_load_recipe: "Falha ao carregar a receita",
    error_failed_load_languages: "Falha ao carregar os idiomas",
  },

  nl: {
    app_subtitle: "Traditionele Franse keuken op je bord.",
    search_placeholder: "Zoeken…",
    open_in_new_tab: "Openen in nieuw tabblad ↗",
    open_recipe_in_new_tab: "Recept openen in nieuw tabblad",
    loading: "Laden…",
    tokens_label: "Tokens",
    aria_search_recipes: "Recepten zoeken",
    error_failed_load_recipes: "Recepten konden niet worden geladen",
    error_search_failed: "Zoeken mislukt",
    error_failed_load_recipe: "Recept kon niet worden geladen",
    error_failed_load_languages: "Talen konden niet worden geladen",
  },

  sv: {
    app_subtitle: "Traditionellt franskt kök på din tallrik.",
    search_placeholder: "Sök…",
    open_in_new_tab: "Öppna i ny flik ↗",
    open_recipe_in_new_tab: "Öppna recept i ny flik",
    loading: "Laddar…",
    tokens_label: "Token",
    aria_search_recipes: "Sök recept",
    error_failed_load_recipes: "Det gick inte att läsa in recept",
    error_search_failed: "Sökning misslyckades",
    error_failed_load_recipe: "Det gick inte att läsa in receptet",
    error_failed_load_languages: "Det gick inte att läsa in språk",
  },

  fi: {
    app_subtitle: "Perinteistä ranskalaista ruokaa lautasellasi.",
    search_placeholder: "Hae…",
    open_in_new_tab: "Avaa uudessa välilehdessä ↗",
    open_recipe_in_new_tab: "Avaa resepti uudessa välilehdessä",
    loading: "Ladataan…",
    tokens_label: "Tokenit",
    aria_search_recipes: "Hae reseptejä",
    error_failed_load_recipes: "Reseptien lataus epäonnistui",
    error_search_failed: "Haku epäonnistui",
    error_failed_load_recipe: "Reseptin lataus epäonnistui",
    error_failed_load_languages: "Kielten lataus epäonnistui",
  },

  da: {
    app_subtitle: "Traditionel fransk mad på din tallerken.",
    search_placeholder: "Søg…",
    open_in_new_tab: "Åbn i ny fane ↗",
    open_recipe_in_new_tab: "Åbn opskriften i en ny fane",
    loading: "Indlæser…",
    tokens_label: "Tokens",
    aria_search_recipes: "Søg efter opskrifter",
    error_failed_load_recipes: "Kunne ikke indlæse opskrifter",
    error_search_failed: "Søgning mislykkedes",
    error_failed_load_recipe: "Kunne ikke indlæse opskrift",
    error_failed_load_languages: "Kunne ikke indlæse sprog",
  },

  pl: {
    app_subtitle: "Tradycyjna kuchnia francuska na Twoim talerzu.",
    search_placeholder: "Szukaj…",
    open_in_new_tab: "Otwórz w nowej karcie ↗",
    open_recipe_in_new_tab: "Otwórz przepis w nowej karcie",
    loading: "Ładowanie…",
    tokens_label: "Tokeny",
    aria_search_recipes: "Szukaj przepisów",
    error_failed_load_recipes: "Nie udało się wczytać przepisów",
    error_search_failed: "Wyszukiwanie nie powiodło się",
    error_failed_load_recipe: "Nie udało się wczytać przepisu",
    error_failed_load_languages: "Nie udało się wczytać języków",
  },

  cs: {
    app_subtitle: "Tradiční francouzská kuchyně na tvém talíři.",
    search_placeholder: "Hledat…",
    open_in_new_tab: "Otevřít v nové záložce ↗",
    open_recipe_in_new_tab: "Otevřít recept v nové záložce",
    loading: "Načítání…",
    tokens_label: "Tokeny",
    aria_search_recipes: "Hledat recepty",
    error_failed_load_recipes: "Nepodařilo se načíst recepty",
    error_search_failed: "Hledání se nezdařilo",
    error_failed_load_recipe: "Nepodařilo se načíst recept",
    error_failed_load_languages: "Nepodařilo se načíst jazyky",
  },

  tr: {
    app_subtitle: "Geleneksel Fransız mutfağı tabağınızda.",
    search_placeholder: "Ara…",
    open_in_new_tab: "Yeni sekmede aç ↗",
    open_recipe_in_new_tab: "Tarifi yeni sekmede aç",
    loading: "Yükleniyor…",
    tokens_label: "Tokenlar",
    aria_search_recipes: "Tarifleri ara",
    error_failed_load_recipes: "Tarifler yüklenemedi",
    error_search_failed: "Arama başarısız",
    error_failed_load_recipe: "Tarif yüklenemedi",
    error_failed_load_languages: "Diller yüklenemedi",
  },

  ru: {
    app_subtitle: "Традиционная французская кухня на вашей тарелке.",
    search_placeholder: "Поиск…",
    open_in_new_tab: "Открыть в новой вкладке ↗",
    open_recipe_in_new_tab: "Открыть рецепт в новой вкладке",
    loading: "Загрузка…",
    tokens_label: "Токены",
    aria_search_recipes: "Искать рецепты",
    error_failed_load_recipes: "Не удалось загрузить рецепты",
    error_search_failed: "Поиск не удался",
    error_failed_load_recipe: "Не удалось загрузить рецепт",
    error_failed_load_languages: "Не удалось загрузить языки",
  },

  zh: {
    app_subtitle: "传统法式美味在你盘中。",
    search_placeholder: "搜索…",
    open_in_new_tab: "在新标签页中打开 ↗",
    open_recipe_in_new_tab: "在新标签页中打开食谱",
    loading: "加载中…",
    tokens_label: "标记",
    aria_search_recipes: "搜索食谱",
    error_failed_load_recipes: "无法加载食谱",
    error_search_failed: "搜索失败",
    error_failed_load_recipe: "无法加载食谱",
    error_failed_load_languages: "无法加载语言",
  },

  "zh-hant": {
    app_subtitle: "傳統法式美味在你盤中。",
    search_placeholder: "搜尋…",
    open_in_new_tab: "在新分頁中開啟 ↗",
    open_recipe_in_new_tab: "在新分頁中開啟食譜",
    loading: "載入中…",
    tokens_label: "標記",
    aria_search_recipes: "搜尋食譜",
    error_failed_load_recipes: "無法載入食譜",
    error_search_failed: "搜尋失敗",
    error_failed_load_recipe: "無法載入食譜",
    error_failed_load_languages: "無法載入語言",
  },

  ja: {
    app_subtitle: "伝統的なフランス料理をあなたの皿に。",
    search_placeholder: "検索…",
    open_in_new_tab: "新しいタブで開く ↗",
    open_recipe_in_new_tab: "レシピを新しいタブで開く",
    loading: "読み込み中…",
    tokens_label: "トークン",
    aria_search_recipes: "レシピを検索",
    error_failed_load_recipes: "レシピを読み込めませんでした",
    error_search_failed: "検索に失敗しました",
    error_failed_load_recipe: "レシピを読み込めませんでした",
    error_failed_load_languages: "言語を読み込めませんでした",
  },

  ko: {
    app_subtitle: "전통 프랑스 요리를 당신의 접시에.",
    search_placeholder: "검색…",
    open_in_new_tab: "새 탭에서 열기 ↗",
    open_recipe_in_new_tab: "레시피를 새 탭에서 열기",
    loading: "로딩 중…",
    tokens_label: "토큰",
    aria_search_recipes: "레시피 검색",
    error_failed_load_recipes: "레시피를 불러오지 못했습니다",
    error_search_failed: "검색에 실패했습니다",
    error_failed_load_recipe: "레시피를 불러오지 못했습니다",
    error_failed_load_languages: "언어를 불러오지 못했습니다",
  },

  ar: {
    app_subtitle: "المطبخ الفرنسي التقليدي في طبقك.",
    search_placeholder: "ابحث…",
    open_in_new_tab: "فتح في علامة تبويب جديدة ↗",
    open_recipe_in_new_tab: "فتح الوصفة في علامة تبويب جديدة",
    loading: "جارٍ التحميل…",
    tokens_label: "الرموز",
    aria_search_recipes: "ابحث عن وصفات",
    error_failed_load_recipes: "فشل تحميل الوصفات",
    error_search_failed: "فشل البحث",
    error_failed_load_recipe: "فشل تحميل الوصفة",
    error_failed_load_languages: "فشل تحميل اللغات",
  },

  hi: {
    app_subtitle: "पारंपरिक फ्रांसीसी व्यंजन आपकी थाली में।",
    search_placeholder: "खोजें…",
    open_in_new_tab: "नई टैब में खोलें ↗",
    open_recipe_in_new_tab: "नई टैब में रेसिपी खोलें",
    loading: "लोड हो रहा है…",
    tokens_label: "टोकन",
    aria_search_recipes: "रेसिपी खोजें",
    error_failed_load_recipes: "रेसिपी लोड नहीं हो सकीं",
    error_search_failed: "खोज विफल हुई",
    error_failed_load_recipe: "रेसिपी लोड नहीं हो सकी",
    error_failed_load_languages: "भाषाएँ लोड नहीं हो सकीं",
  },
};

export function t(lang: LanguageCode, key: I18nKey): string {
  const normalized = normalizeLanguageCode(lang || DEFAULT_LANGUAGE);
  const base = normalized.split("-")[0];

  // Try exact match
  const exact = translations[normalized]?.[key];
  if (exact) return exact;

  // Try base language
  const baseVal = translations[base]?.[key];
  if (baseVal) return baseVal;

  // Try default language (French)
  const frVal = translations[DEFAULT_LANGUAGE]?.[key as I18nKey];
  if (frVal) return frVal;

  // Last resort: English
  const enVal = translations["en"]?.[key as I18nKey];
  if (enVal) return enVal;

  // Fallback to key name if missing
  return key;
}

