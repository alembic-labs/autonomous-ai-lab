import { Hero } from "@/components/home/Hero";
import { LiveStatus } from "@/components/home/LiveStatus";
import { LabStats } from "@/components/home/LabStats";
import { RecentFolds } from "@/components/home/RecentFolds";

export default function HomePage() {
  return (
    <>
      <Hero />
      <LiveStatus />
      <LabStats />
      <RecentFolds />
    </>
  );
}
