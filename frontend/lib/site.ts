const configuredSiteUrl = process.env.NEXT_PUBLIC_SITE_URL?.trim();

export const SITE_URL = (configuredSiteUrl || "http://localhost:3000").replace(
  /\/$/,
  "",
);
export const SITE_NAME = "Sitemyra";
export const PUBLIC_CONTACT_EMAIL = "info@sitemyra.com";
export const FOUNDER_PHONE = "+30 6976901145";

export function getPublicContactEmail() {
  const value = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim() || PUBLIC_CONTACT_EMAIL;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? value : PUBLIC_CONTACT_EMAIL;
}

export const SITE_DESCRIPTION =
  "Monitor competitor pricing, pages and content automatically and get alerted when something changes.";

export const FOUNDER_LINKS = [
  {
    label: "GitHub",
    href: "https://github.com/moaber231",
  },
  {
    label: "LinkedIn",
    href: "https://www.linkedin.com/in/konstantinos-gkogkos-b8a623228/",
  },
  {
    label: "Portfolio",
    href: "https://konstantinos-gkogkos-portfolio.netlify.app/",
  },
] as const;

export function absoluteUrl(path = "/") {
  return new URL(path, SITE_URL).toString();
}
