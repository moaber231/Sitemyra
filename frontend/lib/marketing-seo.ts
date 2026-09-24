import type { Metadata } from "next";

import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";

type MarketingMetadataInput = {
  title: string;
  description: string;
  path: string;
  noIndex?: boolean;
};

export function marketingMetadata({
  title,
  description,
  path,
  noIndex = false,
}: MarketingMetadataInput): Metadata {
  const canonical = path === "/" ? "/" : path;
  const socialTitle =
    path === "/"
      ? "Sitemyra — Know when your competitors change."
      : `${title} — ${SITE_NAME}`;

  return {
    title,
    description,
    alternates: {
      canonical,
    },
    openGraph: {
      type: "website",
      url: path,
      siteName: SITE_NAME,
      title: socialTitle,
      description,
      images: [
        {
          url: "/opengraph-image",
          width: 1200,
          height: 630,
          alt: "Sitemyra — Know when your competitors change.",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: socialTitle,
      description,
      images: ["/opengraph-image"],
    },
    robots: noIndex
      ? {
          index: false,
          follow: false,
        }
      : {
          index: true,
          follow: true,
        },
  };
}

export { SITE_DESCRIPTION, SITE_NAME, SITE_URL };
