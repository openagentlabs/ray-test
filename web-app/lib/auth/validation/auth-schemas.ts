import { z } from "zod";

export const LoginFormSchema = z.object({
  email: z.email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});

export type LoginFormInput = z.infer<typeof LoginFormSchema>;
