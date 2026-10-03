import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono, Open_Sans, Source_Code_Pro } from "next/font/google";
import { LandingLangProvider } from "@/components/LandingLang";
import { PwaRegister } from "@/components/PwaRegister";
import "./globals.css";
import "./shell.css";

const openSans = Open_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-open-sans",
  weight: ["400", "500", "600", "700"],
});

const sourceCodePro = Source_Code_Pro({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-source-code",
  weight: ["400", "600", "700"],
});

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
  weight: ["400", "500", "600", "700", "800"],
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
  themeColor: "#0b0f14",
};

export const metadata: Metadata = {
  title: "Casuya Treble",
  description: "Over 1.5 trebles for BetPawa",
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
      className={`${openSans.variable} ${sourceCodePro.variable} ${inter.variable} ${jetbrains.variable}`}
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
