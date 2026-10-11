import type { Metadata } from "next";
import { IndexView } from "@/components/IndexView";
import "./landing.css";

export const metadata: Metadata = {
  title: "Casuya Treble: football slips from BetPawa odds",
  description:
    "Casuya reads today's BetPawa Tanzania prices and builds one football slip of one to four legs — Over 1.5 goals or corners — priced 1.30 to 6.00.",
};

export default function Page() {
  return <IndexView />;
}
