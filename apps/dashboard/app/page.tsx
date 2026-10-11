import type { Metadata } from "next";
import { IndexView } from "@/components/IndexView";
import "./landing.css";

export const metadata: Metadata = {
  title: "Casuya Treble: Over 1.5 football slips",
  description:
    "Casuya checks today's football matches and shows a slip of one to four teams only when the combined price lands between 1.30 and 6.00.",
};

export default function Page() {
  return <IndexView />;
}
