"""Monitoring recipes — one-click monitoring presets.

A recipe is a **code-level** definition, not user data: it names the kinds
of page worth watching, the check cadence, and whether a product watch
should be attached. Keeping it in code means it can be reviewed, versioned
and tested, and it can never be edited by a user into something unsafe.

The goal is that an SMB user picks "Pricing Watch" and never touches a
URL, a selector, or a cadence.
"""

from .classify import (
    BLOG,
    CAREERS,
    CHANGELOG,
    DOCS,
    FAQ,
    FEATURES,
    HOMEPAGE,
    PRICING,
    PRODUCT,
    PROMOTIONS,
    REVIEWS,
    VARIANTS,
)
from .targets import target_value

PRICING_WATCH = "pricing"
PRODUCT_WATCH_RECIPE = "product"
FEATURE_WATCH = "features"
MARKETING_WATCH = "marketing"
SEO_WATCH = "seo"
HIRING_WATCH = "hiring"
ECOMMERCE_WATCH = "ecommerce"
EVERYTHING_WATCH = "everything"

# Target-kind priority inside a recipe (earlier = more central). The
# activation endpoint uses this to decide what to create when a plan limit
# means it can only build part of the recipe.
RECIPES = {
    PRICING_WATCH: {
        "slug": PRICING_WATCH,
        "name": "Pricing Watch",
        "description": "Follow the prices and plans a competitor publishes.",
        "kinds": (PRICING, PROMOTIONS, PRODUCT),
        "check_interval": 900,
        "product_watch": True,
    },
    PRODUCT_WATCH_RECIPE: {
        "slug": PRODUCT_WATCH_RECIPE,
        "name": "Product Watch",
        "description": "Track one product page: price, availability, variants and copy.",
        "kinds": (PRODUCT, VARIANTS, REVIEWS),
        "check_interval": 900,
        "product_watch": True,
    },
    FEATURE_WATCH: {
        "slug": FEATURE_WATCH,
        "name": "Feature Watch",
        "description": "Watch the capability list, documentation and release notes.",
        "kinds": (FEATURES, CHANGELOG, DOCS),
        "check_interval": 3600,
        "product_watch": False,
    },
    MARKETING_WATCH: {
        "slug": MARKETING_WATCH,
        "name": "Marketing Watch",
        "description": "Follow homepage messaging, promotions and editorial output.",
        "kinds": (HOMEPAGE, PROMOTIONS, BLOG),
        "check_interval": 3600,
        "product_watch": False,
    },
    SEO_WATCH: {
        "slug": SEO_WATCH,
        "name": "SEO Watch",
        "description": "Watch titles, descriptions, FAQ and documentation pages.",
        "kinds": (HOMEPAGE, FAQ, DOCS, BLOG),
        "check_interval": 3600,
        "product_watch": False,
    },
    HIRING_WATCH: {
        "slug": HIRING_WATCH,
        "name": "Hiring Watch",
        "description": "See when a competitor opens or closes roles.",
        "kinds": (CAREERS, HOMEPAGE),
        "check_interval": 3600,
        "product_watch": False,
    },
    ECOMMERCE_WATCH: {
        "slug": ECOMMERCE_WATCH,
        "name": "E-commerce Watch",
        "description": "Product, price, availability, variants, reviews and shipping.",
        "kinds": (PRODUCT, PRICING, VARIANTS, REVIEWS, PROMOTIONS),
        "check_interval": 900,
        "product_watch": True,
    },
    EVERYTHING_WATCH: {
        "slug": EVERYTHING_WATCH,
        "name": "Everything Watch",
        "description": "Monitor every page Sitemyra found worth watching.",
        "kinds": (),
        "check_interval": 1800,
        "product_watch": True,
    },
}

DEFAULT_RECIPE = EVERYTHING_WATCH


def get_recipe(slug: str) -> dict:
    recipe = RECIPES.get((slug or "").strip().lower())
    if recipe is None:
        recipe = RECIPES[DEFAULT_RECIPE]
    return recipe


def list_recipes() -> list:
    return [
        {
            "slug": recipe["slug"],
            "name": recipe["name"],
            "description": recipe["description"],
            "check_interval": recipe["check_interval"],
            "product_watch": recipe["product_watch"],
            "target_kinds": list(recipe["kinds"]),
        }
        for recipe in RECIPES.values()
    ]


def select_targets(targets, slug: str):
    """Filter discovered targets down to what a recipe asks for.

    An empty ``kinds`` tuple means "everything", which is how
    Everything Watch is expressed.
    """
    recipe = get_recipe(slug)
    kinds = recipe["kinds"]
    if not kinds:
        return list(targets)
    # Always keep the submitted page: the user pasted it on purpose.
    primary = [target for target in targets if target_value(target, "is_primary", False)]
    rest = [target for target in targets if not target_value(target, "is_primary", False)]
    return primary + [target for target in rest if target_value(target, "kind") in kinds]


def wants_product_watch(slug: str) -> bool:
    return bool(get_recipe(slug)["product_watch"])


def check_interval_for(slug: str) -> int:
    return int(get_recipe(slug)["check_interval"])
