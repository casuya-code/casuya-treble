import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { LandingLangProvider } from "@/components/LandingLang";
import { PwaRegister } from "@/components/PwaRegister";
import "./globals.css";
import "./shell.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
  weight: ["400", "500", "600", "700"],
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains",
  weight: ["500", "700"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#fbfbf8",
};

export const metadata: Metadata = {
  title: "Casuya Treble",
  description: "Over 1.5 football slips (2.10–2.50) for BetPawa",
  applicationName: "Casuya Treble",
  appleWebApp: {
    capable: true,
    title: "Casuya Treble",
    statusBarStyle: "default",
  },
  icons: {
    icon: [{ url: "/icons/favicon.svg", type: "image/svg+xml" }],
    shortcut: "/icons/favicon.svg",
    apple: [{ url: "/icons/icon-192.svg", type: "image/svg+xml" }],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrains.variable}`}
      suppressHydrationWarning
    >
      <body className="app-body" suppressHydrationWarning>
        <LandingLangProvider>
          <PwaRegister />
          <div className="device-screen">{children}</div>
        </LandingLangProvider>
      </body>
    </html>
  );
}
