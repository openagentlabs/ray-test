# EXLdecision.AI

## Transform Your Data into Actionable Intelligence

The most comprehensive analytics platform with AI-powered insights, synthetic data generation, and advanced modeling capabilities designed for modern businesses.

<div align="left">

<small>

| | |
|:--|:--|
| **Version** | 1.0.0 |
| **Updated** | 2026-06-14 12:00 UTC |
| **Owner** | platform@example.com |

</small>

</div>

---

# Web-app page authoring rules (Cursor agent guide)

Human-oriented rules for creating and editing pages in **`web-app/`** (Manager Web, Next.js on port **8811**). Follow these whenever adding routes, page containers, layouts, auth flows, or component template galleries.

**Canonical references**

| Topic | Path |
|-------|------|
| Responsive design (four viewports, shells, primitives) | [web-design.md](web-design.md) · agent rule **`.cursor/rules/web-design/web-design.mdc`** |
| App root & run | `web-app/README.md` |
| EXL theme tokens | `web-app/app/globals.css` |
| shadcn config | `web-app/components.json` |
| Monorepo boundaries | `.cursor/rules/solution/solution.mdc` |
| TypeScript / validation | `.cursor/rules/typescript/typescript.mdc` |

---

## 1. Scope and boundaries

1. **`web-app/` is presentation-only.** UI, layout, navigation, forms, client-side feedback, and thin route handlers only. No product domain logic, persistence, authz decisions, or business rules in `web-app/lib/` beyond presentation adapters.
2. **Do not copy layout or styling from other apps** (e.g. `bu-analytics-gen-ai-midas/frontend`, `aspire.svc/`). Reuse **text or product copy** only when explicitly requested. All visual design must conform to **`web-app`** theme and existing patterns.
3. **Use semantic theme tokens only** — `bg-background`, `text-foreground`, `text-muted-foreground`, `border-border`, `bg-card`, `text-primary`, `shadow-surface`, etc. Never hard-code EXL hex/orange values in components when a token exists in `globals.css`.
4. **Use shadcn/ui primitives** from `web-app/components/ui/`. Add new primitives via the project’s shadcn setup (`components.json`, `base-nova` style) before inventing bespoke controls.

---

## 2. Mandatory page file structure

Every new page **must** use the thin-route + page-container pattern. **Never** put UI logic or presentational components directly in `app/**/page.tsx`.

### 2.1 Route layer (`app/`)

- **Role:** Thin route container only — import and render the matching page component.
- **Max content:** default export that returns `<XxxPage />` (or equivalent).
- **Forbidden:** forms, state, business logic, inline JSX sections, or direct imports from `components/ui/` in route files.

```tsx
// app/pages/user/sign-in/page.tsx
import { SignInPage } from "@/pages-components/user/sign-in/sign-in-page";

export default function SignInRoute() {
  return <SignInPage />;
}
```

### 2.2 Page entry (`pages-components/`)

- **Path:** `pages-components/<area>/<page-name>/<page-name>-page.tsx`
- **Role:** Page entry — renders the page container only.
- **Export:** named export `XxxPage`.

```tsx
// pages-components/user/sign-in/sign-in-page.tsx
import { SignInPageContainer } from "./components/page-container";

export function SignInPage() {
  return <SignInPageContainer />;
}
```

### 2.3 Page container (`components/page-container.tsx`)

- **Path:** `pages-components/<area>/<page-name>/components/page-container.tsx`
- **Role:** **All page UI logic and composition** live here (or in sibling files under `components/`).
- **Naming:** file must be `page-container.tsx`; export `XxxPageContainer`.
- **Forbidden:** placing interactive UI only in `*-page.tsx` or in `app/**/page.tsx`.

### 2.4 Subcomponents

- **Path:** `pages-components/<area>/<page-name>/components/<name>.tsx`
- **Role:** Presentational or focused UI pieces used by the page container (forms, panels, sections).
- **Rule:** Route → page entry → **page container** → subcomponents. Never skip the container.

### 2.5 Folder naming for grouped pages

| Page type | App route | `pages-components` folder |
|-----------|-----------|----------------------------|
| Workspace page | `app/pages/(workspace)/<name>/page.tsx` | `pages-components/<name>/` |
| User / auth page | `app/pages/user/<name>/page.tsx` | `pages-components/user/<name>/` |
| Template group | `app/pages/templates/<group>/page.tsx` | `pages-components/templates/<group>/` |
| Marketing / root | `app/page.tsx` | `pages-components/home/` |

Each logical page gets **its own folder** (e.g. `sign-in/`, `forgot-password/`, not shared `page-container.tsx` at parent level unless it is a true shared layout component).

---

## 3. Layout shells (route groups)

Pages must render inside the **correct layout shell**. Do not mount auth or template pages inside the dashboard sidebar.

### 3.1 Workspace pages (sidebar app)

- **Routes:** `app/pages/(workspace)/**` — dashboard, documents, settings, testing, etc.
- **Layout:** `app/pages/(workspace)/layout.tsx` → `DashboardShell` (sidebar + header).
- **Page containers:** content only; shell is provided by layout.

### 3.2 Public / auth pages (no sidebar)

- **Routes:** `app/pages/user/**` — sign-in, forgot-password, register, etc.
- **Layout:** `app/pages/user/layout.tsx` → **`MarketingPageShell`** with default **`MarketingHeader`**.
- **Shared auth layout components:** `pages-components/user/components/` (e.g. `auth-page-layout.tsx`, `AuthPanel`).

### 3.3 Component template gallery

- **Index route:** `/pages/templates` — **`TEMPLATES_INDEX_PATH`** in `web-app/lib/templates/template-groups.ts`.
- **Layout:** `app/pages/templates/layout.tsx` → **`MarketingPageShell`** with **`MarketingHeader`** + template-specific **`TemplatesHeaderTrailing`** (gallery link + URL badge).
- **Page content:** every template index and group page must use **`TemplatesPageLayout`** for title, description, breadcrumb/back link, and gallery URL.
- **Group demos:** use **`TemplateGroupPageLayout`** / `CodeDemoSection` from `pages-components/templates/components/template-demo-kit.tsx`.

**Rule:** Do not duplicate marketing header chrome inside page containers; use **`components/layout/marketing-header.tsx`** and **`MarketingPageShell`**.

### 3.4 Marketing home

- **Route:** `app/page.tsx` → `pages-components/home/home-page.tsx`.
- **Layout:** **`MarketingPageShell`** with nav items + footer; hero content only in page container.

---

## 4. Visual design and Material Design alignment

Apply [Material Design](https://m3.material.io/) **principles**, styled with the **EXL / web-app theme** — not Material’s default purple palette.

### 4.1 Hierarchy and focus

- One **primary action** per screen (filled primary button).
- Clear **title → supporting text → content → actions** order.
- Use `text-muted-foreground` for secondary copy; `font-semibold` / size scale for headings.

### 4.2 Surfaces and elevation

- Cards: `rounded-xl` or `rounded-2xl`, `border border-border`, `bg-card`, `shadow-surface`.
- Page sections: `max-w-6xl` / `xl:max-w-7xl` centered containers, consistent horizontal padding (`px-4 sm:px-6 lg:px-8`).

### 4.3 Touch and accessibility

- Minimum touch targets on mobile: buttons **`h-11`** (or `size` lg) where appropriate; **`h-10`** / `md:h-9` on larger breakpoints.
- Associate every input with **`Label`** + `htmlFor` / `id`.
- Errors: `role="alert"`, `aria-invalid`, **`Alert`** with `variant="destructive"`.
- Loading: disable controls, `aria-busy` on forms, spinner on primary button.
- Password fields: offer show/hide control with `aria-label`.

### 4.4 Edge cases (mandatory for auth and forms)

- Client-side validation before submit (empty, format, min length).
- Distinct **loading**, **error**, and **success** states (e.g. forgot-password confirmation without account enumeration).
- Network failure messaging; do not leave user on silent failure.
- Keyboard: logical tab order; submit via Enter in forms.
- Responsive: no horizontal overflow on phone; collapsible side content on small screens.

---

## 5. Responsive breakpoints (four targets)

Design and test for all four. Use Tailwind defaults aligned to project usage:

| Target | Breakpoint | Tailwind | Layout notes |
|--------|------------|----------|--------------|
| Smartphone | `< 640px` | default | Single column, full-width cards, stacked actions, compact header |
| Tablet | `640px – 1023px` | `sm:`, `md:` | Increased padding; 2-column grids where appropriate |
| Laptop | `1024px – 1279px` | `lg:` | Optional two-column auth (copy + form); sidebar workspace |
| Desktop | `≥ 1280px` | `xl:` | Wider max-width (`xl:max-w-7xl`); multi-column template grids |

**Rule:** Use responsive grids (`grid-cols-1 sm:grid-cols-2 xl:grid-cols-3`) rather than fixed pixel widths.

---

## 6. Component template gallery rules

When adding or extending **`/pages/templates`**:

1. **Register groups** in `web-app/lib/templates/template-groups.ts` (`TEMPLATE_GROUPS`, `TEMPLATES_INDEX_PATH`).
2. **Index page:** `pages-components/templates/components/page-container.tsx` — Material-inspired **clickable panels** linking to each group; must use `TemplatesPageLayout`.
3. **Group page structure:**
   - `app/pages/templates/<group>/page.tsx` (thin route)
   - `pages-components/templates/<group>/<group>-template-page.tsx` (entry)
   - `pages-components/templates/<group>/components/page-container.tsx` (demos)
4. **Each demo block:** `CodeDemoSection` with live preview, expandable code, **Copy snippet** button.
5. **Coverage:** demonstrate **variants, sizes, and states** (default, disabled, loading, destructive, etc.) for each primitive in the group.
6. **Navigation:** every group page shows **back to template gallery** linking to **`/pages/templates`**; header shows gallery URL + copy on sm+.
7. **New shadcn primitive:** add under `components/ui/`, then add or extend a template group — do not leave primitives undocumentated in the gallery.

---

## 7. Auth and user pages

1. Place under **`app/pages/user/<feature>/`** with matching **`pages-components/user/<feature>/`** tree.
2. Reuse **`AuthPageLayout`** + **`AuthPanel`** for consistent auth chrome.
3. Link sign-in ↔ forgot-password ↔ register with theme **`text-primary`** links.
4. Legacy paths (e.g. `/login`) may redirect to canonical routes (`/pages/user/sign-in`) via thin redirect routes — do not duplicate full pages.
5. Wire to real APIs when available; until then, validate on the client and surface errors in **`Alert`** — never silent mock success for security-sensitive flows without documenting it.

---

## 8. Imports and naming conventions

| Item | Convention |
|------|------------|
| Page entry | `SignInPage`, `DashboardPage`, `ButtonsTemplatePage` |
| Page container | `SignInPageContainer`, `TemplatesPageContainer` |
| Route file | default export `SignInRoute`, `DashboardRoute`, etc. |
| UI primitives | `@/components/ui/*` |
| Layout shell | `@/components/layout/*` — **`MarketingHeader`**, **`MarketingPageShell`** (public), **`DashboardShell`** (workspace) |
| Shared page layouts | `@/pages-components/<area>/components/*` |
| Utils | `@/lib/utils` (`cn`) |
| Config | `@/lib/config/app-config-public` |

---

## 9. Checklist before finishing a new page

- [ ] Route file is thin (imports page entry only).
- [ ] `pages-components/.../<name>-page.tsx` renders `components/page-container.tsx` only.
- [ ] UI logic lives in page container or its `components/` siblings — not in `app/`.
- [ ] Correct layout shell: workspace vs user vs templates vs marketing.
- [ ] EXL semantic tokens only; no copied foreign app styling.
- [ ] Responsive at smartphone, tablet, laptop, desktop.
- [ ] Material hierarchy: one primary action, clear headings, accessible forms.
- [ ] Auth/forms: loading, error, success, and validation edge cases handled.
- [ ] Template groups (if applicable): registered in **`template-groups.ts`**, use **`MarketingPageShell`** + **`TemplatesPageLayout`**, include **`CodeDemoSection`** demos.
- [ ] `npm run build:fast` passes from `web-app/`.

---

## 10. Canonical URLs (reference)

| Page | Path |
|------|------|
| Marketing home | `/` |
| Sign in | `/pages/user/sign-in` |
| Forgot password | `/pages/user/forgot-password` |
| Template gallery (index) | **`/pages/templates`** |
| Template group example | `/pages/templates/buttons` |
| Dashboard (workspace) | `/pages/dashboard` |

Local dev base: `http://localhost:8811` + path above.

- Knowledge: Agent rule for responsive layout and shells — **`.cursor/rules/web-design/web-design.mdc`** (loads on **`web-app/**`** globs).

---

## 11. Anti-patterns (do not do)

- Putting JSX, hooks, or form handlers in `app/**/page.tsx`.
- Skipping `page-container.tsx` and implementing the page in `*-page.tsx` only.
- Mounting sign-in or template demos inside `DashboardShell`.
- Copying MIDAS / aspire / frontend CSS classes, gradients, or nav patterns wholesale.
- Hard-coding colors outside `globals.css` tokens.
- Creating one-off buttons/inputs instead of extending `components/ui/`.
- Adding template group routes without updating `template-groups.ts` and the index panels.
- Duplicating gallery header/back-link logic outside **`MarketingPageShell`** / **`MarketingHeader`** / **`TemplatesPageLayout`**.
