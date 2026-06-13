import { HomePage } from "@/pages-components/home/home-page";
import { MarketingNavigation } from "@/lib/navigation/marketing-navigation";

export default function RootRoute() {
  return <HomePage navigationItems={MarketingNavigation.getItems()} />;
}
