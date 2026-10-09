import type { Metadata } from "next";
import { IndexView } from "@/components/IndexView";
import "./landing.css";

export const metadata: Metadata = {
  title: "Casuya Treble: Over 1.5 football slips",
  description:
    "Casuya checks today's football matches and shows a slip of one to three teams only when the combined price lands between 1.90 and 2.50.",
};

export default function Page() {
  return <IndexView />;
}
