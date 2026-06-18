import { redirect } from "next/navigation";

export default function DashboardAdminRedirect() {
  // Keep backward compatibility if some links still point to /dashboard/admin
  redirect("/admin");
}
