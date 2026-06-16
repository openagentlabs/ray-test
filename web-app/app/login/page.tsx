import { redirect } from "next/navigation";

export default function LoginRedirectRoute() {
  redirect("/pages/user/sign-in");
}
