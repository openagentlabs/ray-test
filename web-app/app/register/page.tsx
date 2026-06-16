import { redirect } from "next/navigation";

export default function RegisterRedirectRoute() {
  redirect("/pages/user/register");
}
