import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "sonner";
import { QueryProvider } from "@/components/providers/query-provider";

export const metadata: Metadata = {
  title: "Apeiro Monitor — Know when the web changes.",
  description: "Monitor important web pages and get alerted when they change, fail, or recover.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          {children}
        </QueryProvider>

        <Toaster position="bottom-right" richColors />
      </body>
    </html>
  );
}