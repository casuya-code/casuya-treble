import type { Metadata } from "next";
import { IndexView } from "@/components/IndexView";
import "./landing.css";

export const metadata: Metadata = {
  title: "Casuya Treble: Over 1.5 football trebles",
  description:
    "Casuya checks today's football matches and shows a treble only when the combined price is at least 3.00.",
};

export default function Page() {
  return <IndexView />;
}
