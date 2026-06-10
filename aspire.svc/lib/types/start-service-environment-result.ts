export type StartServiceEnvironmentResult =
  | { readonly ok: true }
  | { readonly ok: false; readonly message: string };
