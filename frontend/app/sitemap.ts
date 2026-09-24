import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

const publicRoutes = [
  { path: "", priority: 1 },
  { path: "/how-it-works", priority: 0.9 },
  { path: "/pricing", priority: 0.9 },
  { path: "/faq", priority: 0.7 },
  { path: "/about", priority: 0.7 },
  { path: "/contact", priority: 0.6 },
  { path: "/security", priority: 0.6 },
  { path: "/privacy", priority: 0.3 },
  { path: "/terms", priority: 0.3 },
  { path: "/cookies", priority: 0.3 },
];

export default function sitemap(): MetadataRoute.Sitemap {
  return publicRoutes.map(({ path, priority }) => ({
    url: `${SITE_URL}${path}`,
    lastModified: new Date(),
    changeFrequency: "weekly",
    priority,
  }));
}
