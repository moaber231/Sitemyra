import type { Metadata, Viewport } from "next";
import { Calistoga, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import "./marketing.css";
import { Toaster } from "sonner";
import { QueryProvider } from "@/components/providers/query-provider";
import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";

const calistoga = Calistoga({
  subsets: ["latin"],
  display: "swap",
  weight: "400",
  variable: "--font-calistoga",
});

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} — Know when your competitors change.`,
    template: `%s | ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  keywords: [
    "competitor monitoring",
    "competitor price tracking",
    "website change monitoring",
    "competitor website monitoring",
    "pricing change alerts",
  ],
  authors: [{ name: "Konstantinos Gkogkos" }],
  creator: "Konstantinos Gkogkos",
  publisher: SITE_NAME,
  // Public marketing pages set their own canonical URLs. Keeping the root
  // canonical broad would make authenticated routes look like duplicate home
  // pages to crawlers.
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: SITE_NAME,
    title: `${SITE_NAME} — Know when your competitors change.`,
    description: SITE_DESCRIPTION,
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
    title: `${SITE_NAME} — Know when your competitors change.`,
    description: SITE_DESCRIPTION,
    images: ["/opengraph-image"],
  },
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
    apple: "/icon.svg",
  },
  // Marketing pages opt into indexing through marketingMetadata(). Private
  // application routes inherit this safer default instead of looking public.
  robots: {
    index: false,
    follow: false,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "light",
  themeColor: "#fafafa",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${calistoga.variable} ${inter.variable} ${jetbrainsMono.variable}`}
      >
        <QueryProvider>
          {children}
        </QueryProvider>

        <Toaster position="bottom-right" richColors />
      </body>
    </html>
  );
}
