import { AppProvider } from "@/lib/store";
import Shell from "@/components/Shell";

export default function Page() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
