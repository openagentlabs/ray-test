/**
 * Rust-style `Option<T>` for explicit optional values (distinct from `undefined`).
 */

export type Option<T> =
  | { readonly some: true; readonly value: T }
  | { readonly some: false };

export class OptionValue {
  public static some<T>(value: T): Option<T> {
    return { some: true, value };
  }

  public static none<T>(): Option<T> {
    return { some: false };
  }

  public static fromNullable<T>(value: T | null | undefined): Option<T> {
    if (value === null || value === undefined) {
      return OptionValue.none<T>();
    }
    return OptionValue.some(value);
  }

  private constructor() {}
}
