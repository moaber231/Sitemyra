import type { Metadata } from "next";

import { ServicePage } from "@/components/marketing/service-page";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata: Metadata = marketingMetadata({
  title: "Website Construction Services",
  description:
    "Custom, fast, and professional website construction for businesses in Greece and beyond. Packages and monthly care available.",
  path: "/services",
});

export default function ServicesPage() {
  return <ServicePage />;
}
