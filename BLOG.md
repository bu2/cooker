# Cooker, un side‑project qui mijote des recettes (IA) — maintenant en ligne sur LaTambouille.fr

*Blog généré avec l'IA*

> **TL;DR** — J’ai cuisiné un petit projet perso baptisé **Cooker** : un pipeline de génération de recettes + une **galerie web** en FastAPI/React, avec **recherche vectorielle** (LanceDB), **traductions multi‑langues**, **images générées** pour chaque plat, et un **déploiement Docker** sur Scaleway.
> 🧑‍🍳 **Démo** : [LaTambouille.fr](https://LaTambouille.fr) — 🧩 **Code** : [github.com/bu2/cooker](https://github.com/bu2/cooker)

---

## Pourquoi ce projet ?

Je voulais une façon rapide et amusante d’explorer le **text‑to‑recipe** (générer du texte culinaire de qualité), d’y ajouter une **recherche sémantique** utile (“montre‑moi des plats proches de *tagliatelles aux cèpes*”) et de **servir tout ça dans une galerie simple** à parcourir — avec images et traductions. Bref : un terrain de jeu concret pour des briques IA modernes **du prompt à la prod**.

---

## Ce que fait Cooker

* **Génère des recettes** (titre, ingrédients, étapes, conseils) et **leurs images**.
* **Indexe** le corpus avec des **embeddings** et expose une **recherche vectorielle** (ANN).
* **Traduit** et **internationalise l’UI** (français ↔︎ anglais au départ).
* S’auto‑emballe en **Docker** et se déploie sur **Scaleway** (Nginx en front), avec **rotation/persistance des logs**.

---

## La pile technique (vue d’ensemble)

* **Génération**

  * *Code & scripts* : **Codex CLI (GPT‑5 High)** pour accélérer la production de code et de scripts.
  * *Texte des recettes & traductions* : **Mistral API** (dont **Batch** pour réduire les coûts).
  * *Images des recettes* : **OpenAI API** (une image par recette).
* **Recherche & données**

  * **Embeddings** + **LanceDB** (ANN). Passage de **dot‑product** → **cosine similarity**, **sans normalisation** par défaut pour mieux coller au cosine.
  * **tiktoken** pour estimer les **tokens/coûts** en amont.
  * **Export** vers le **TensorFlow Embedding Projector** pour visualiser le corpus.
* **Web app**

  * **Backend** : **FastAPI** (endpoints de recherche, langues, données).
  * **Frontend** : **Vite + React** (galerie, modales de recette, sélecteur de langue, état de recherche **persisté** au changement de langue).
  * **i18n** : toutes les chaînes externalisées, bascule à chaud.
* **Ops**

  * **Dockerfile** unique (frontend build + backend derrière Nginx).
  * **Scaleway** : script de déploiement, config Nginx, **Caddy** pour le local, notes **DNS**, et **log rotation**.

---

## Chronologie éclair (sept. → oct. 2025)

* **14–15 septembre** : scripts de base (génération en français, embeddings, indexation **LanceDB**), estimation de coût via **tiktoken** et export TF Projector.
* **18–21 septembre** : **galerie web** (FastAPI + Vite/React), refactor des scripts sous `scripts/`, ajout du **générateur d’images**.
* **22–27 septembre** : itérations **ANN** (cosine), **traductions** via Ollama/Mistral, **UI multi‑langue**, conservation de la recherche lors d’un switch de langue, **polish** continu du frontend.
* **28–30 septembre** : encore du polish UI/UX, dataset rangé sous `data/`, cohérence des chemins et CSS.
* **3–10 octobre** : **refactor backend**, **i18n complet**, **.env.example** côté frontend, **Docker** + **Scaleway** + **DNS**, ajout d’**AGENTS.md**, **rotation/persistance des logs** côté déploiement.

---

## Architecture (3 blocs)

```
[ Génération (Mistral/OpenAI) ]
    ├─ scripts/generate_recipes.*            # texte
    ├─ scripts/generate_recipe_images.py     # images
    └─ scripts/generate_recipe_translations.*# traductions
             │
             ▼
[ Embeddings & Index (LanceDB) ]
    ├─ scripts/embed_recipes.py              # embeddings + tiktoken cost
    └─ scripts/index_recipes.py              # ANN (cosine)
             │
             ▼
[ Galerie Web ]
    ├─ backend/main.py (FastAPI)             # /search, /languages, /recipes...
    └─ frontend (Vite/React + i18n)          # UI, modales, switch de langue
```

---

## Quelques décisions clés

* **Cosine plutôt que dot‑product**
  Les premiers tests au **dot‑product** n’étaient pas assez robustes. En passant à la **cosine similarity** (et en **désactivant la normalisation** par défaut), j’ai obtenu un **classement plus pertinent** sur des requêtes “proches mais pas identiques”.

* **Batch Mistral pour maîtriser les coûts**
  Les jobs de génération/traduction passent en **batch** quand c’est possible → réduction du **latency/overhead** API et **des coûts**. Associé à **tiktoken**, ça évite les mauvaises surprises.

* **UX multi‑langue**
  Le **sélecteur de langue** n’écrase pas le **contexte de recherche** : on peut basculer FR/EN **sans perdre la requête**.
  L’API expose `/languages` et adapte la **recherche locale** en fonction de la langue ciblée.

* **DevEx & Déploiement**
  Un **Dockerfile** unique construit le frontend, embarque le backend et sert le tout via **Nginx**.
  Le script **Scaleway** gère les mises à jour de container, la synchro d’objets et la **rotation/persistance** des logs. **Caddy** sert au confort dev local.

---

## Ce que j’ai appris

* **Itérer tôt sur la métrique de similarité** change vraiment la qualité perçue.
* **Garder la recherche** quand on change de langue semble un détail… jusqu’à ce qu’on l’enlève.
* **Anticiper les coûts** (tiktoken + batch) évite de rogner ensuite sur la qualité.
* **Un Dockerfile soigné** simplifie la vie en prod et en local.

---

## Et la suite ?

* Ajouter **plus de langues** et un **sélecteur de tonalité** (familier/neutre).
* **Filtrage** (temps, régime, allergènes).
* Mini‑**notebook d’évaluation** des résultats (précision, diversité).
* **Avant/Après** des prompts avec captures (pour documenter les effets).

---

## Remerciements & crédits

* **Codex CLI (GPT‑5 High)** pour m’avoir aidé à produire rapidement le code et les scripts.
* **Mistral API** pour le texte et les **traductions**.
* **OpenAI API** pour les **images** des recettes.

---

## Essayez et dites‑moi ce que vous en pensez !

* 🍽️ **En ligne** : [LaTambouille.fr](https://LaTambouille.fr)
* 🧩 **Code source** : [github.com/bu2/cooker](https://github.com/bu2/cooker)
