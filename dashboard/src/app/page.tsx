import { Report } from "@/components/Report";
import { loadDataset } from "@/lib/load";

export default function Page() {
  const data = loadDataset();
  return <Report data={data} repoUrl={process.env.NEXT_PUBLIC_REPO_URL} />;
}
