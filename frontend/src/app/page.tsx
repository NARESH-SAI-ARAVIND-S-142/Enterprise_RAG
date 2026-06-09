import { redirect } from "next/navigation";

export default function RootPage() {
  // Root page redirects to login — the dashboard layout handles auth check
  redirect("/login");
}
