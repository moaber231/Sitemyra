"use client";

import { useState } from "react";

import type { Recipe } from "@/lib/api/intelligence";

/**
 * One-click monitoring recipes.
 *
 * The point of these is to remove configuration, not to add it: a user
 * picks the question they want answered ("what are they charging?") and
 * Sitemyra decides which pages and signals to watch.
 */
export function RecipePicker({
  recipes,
  selected,
  onSelect,
}: {
  recipes: Recipe[];
  selected: string;
  onSelect: (slug: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? recipes : recipes.slice(0, 4);

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold tracking-tight text-foreground">Start from a recipe</p>
        <p className="text-xs text-muted-foreground">Optional — “Monitor everything” uses all targets.</p>
      </div>

      <div role="radiogroup" aria-label="Monitoring recipe" className="mt-3 grid gap-2 sm:grid-cols-2">
        {visible.map((recipe) => {
          const active = recipe.slug === selected;
          return (
            <button
              key={recipe.slug}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onSelect(active ? "" : recipe.slug)}
              className={`rounded-2xl border p-4 text-left transition duration-200 ${
                active
                  ? "border-accent/40 bg-accent/5 shadow-[0_8px_24px_rgb(0_82_255_/_0.10)]"
                  : "border-border bg-card hover:-translate-y-0.5 hover:border-accent/25 hover:shadow-sm"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="text-sm font-semibold text-foreground">{recipe.name}</span>
                {recipe.product_watch ? (
                  <span className="apeiro-badge bg-accent/10 text-accent">Product data</span>
                ) : null}
              </div>
              <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{recipe.description}</p>
            </button>
          );
        })}
      </div>

      {recipes.length > 4 ? (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-2.5 text-xs font-semibold text-accent underline decoration-accent/30 underline-offset-4 hover:text-accent-secondary"
        >
          {expanded ? "Show fewer recipes" : `Show all ${recipes.length} recipes`}
        </button>
      ) : null}
    </div>
  );
}
