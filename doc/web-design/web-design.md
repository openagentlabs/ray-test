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

# Web-app responsive design guide

A practical guide for **junior web designers** and **junior web developers** working on **`web-app/`** (Manager Web, Next.js on port **8811**).

This document explains **how we handle smartphone, tablet, laptop, and desktop screen sizes**, what the **gold standard** approach is, and how to build pages that are **easy to implement and maintain** with **no responsive gaps**.

**Related docs**

| Topic | Path |
|-------|------|
| Cursor agent rules (auto-attaches on `web-app/` edits) | `.cursor/rules/web-design/web-design.mdc` |
| Page file structure and routes | [web-app-pages.md](web-app-pages.md) |
| App run instructions | `web-app/README.md` |
| Theme colors and tokens | `web-app/app/globals.css` |
| UI primitives (buttons, inputs, …) | `web-app/components/ui/` |

---

## 1. What this guide covers

### 1.1 Who should read this

- **Designers** planning layouts, spacing, navigation, and component behavior at different screen widths.
- **Developers** implementing pages in `web-app/pages-components/` and layout shells in `web-app/components/layout/`.

You do **not** need to memorize every Tailwind class. You **do** need to understand **where responsive behavior lives** in our codebase so every page behaves consistently.

### 1.2 What “responsive” means here

**Responsive design** means **one page** adapts smoothly as the browser window gets wider or narrower. We do **not** build separate pages for phone vs desktop.

Instead:

- The **same URL** works on all devices (for example `/pages/dashboard`).
- **CSS breakpoints** change layout, spacing, and visibility.
- **Shared layout shells** handle navigation and sidebars so individual pages do not re-solve mobile menus.

### 1.3 Our four design targets

We design and test for **four** viewport groups. These match Tailwind CSS defaults used in `web-app/`.

| Target | Screen width | Tailwind prefixes | Typical layout |
|--------|--------------|-------------------|----------------|
| **Smartphone** | below 640px | *(none — default styles)* | Single column, stacked actions, compact header, touch-friendly controls |
| **Tablet** | 640px – 1023px | `sm:`, `md:` | More padding, 2-column grids where useful |
| **Laptop** | 1024px – 1279px | `lg:` | Workspace sidebar, two-column auth (copy + form) |
| **Desktop** | 1280px and up | `xl:` | Wider max content width, denser multi-column grids |

**Designer tip:** Think in **ranges**, not exact device models. An iPhone and a small Android phone both fall under **Smartphone**. An iPad and a landscape phone may fall under **Tablet**.

**Developer tip:** Tailwind is **mobile-first**. Unprefixed classes apply to the smallest screens. Prefixes like `sm:`, `lg:`, and `xl:` apply **at that width and above**.

---

## 2. Gold standard architecture (read this first)

This is the **approved, maintainable** way to implement responsive layouts in `web-app/`. Follow this unless a tech lead approves an exception.

### 2.1 The big idea: three layers

Responsive behavior is split into **three layers**. Each layer has a clear job. Page authors should mostly work in **Layer 3** only.

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1 — Layout shells (fix once, all pages benefit)     │
│  MarketingPageShell, DashboardShell, AuthPageLayout         │
│  Owns: header, sidebar, mobile drawer, main chrome          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 2 — Layout primitives (reuse on every page)          │
│  PageSection, ResponsiveGrid, ShowFrom / HideFrom           │
│  Owns: max-width, padding, grid columns, show/hide rules    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 3 — Page content (one page-container per route)      │
│  Forms, cards, copy, tables, charts                         │
│  Owns: page-specific content only — not global nav          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Why this is the gold standard

| Benefit | Explanation |
|---------|-------------|
| **No gaps** | Mobile navigation and sidebar behavior live in **shells**. Fix the shell once; every page inherits the fix. |
| **Easy maintenance** | Business logic (forms, validation, API calls) lives in **one** `page-container.tsx`, not four copies. |
| **Consistent look** | Spacing and grids come from **primitives**, not copy-pasted Tailwind on every file. |
| **Resize-safe** | When a user rotates a tablet or resizes a window, CSS adapts instantly. Separate “mobile pages” would break on resize. |

### 2.3 What we do **not** do

Do **not** create separate page components per screen size, for example:

```
❌ pages-components/dashboard/smartphone/page-container.tsx
❌ pages-components/dashboard/tablet/page-container.tsx
❌ pages-components/dashboard/laptop/page-container.tsx
❌ pages-components/dashboard/desktop/page-container.tsx
```

That pattern duplicates logic, causes bugs to drift between files, and is **not** our standard.

---

## 3. Layer 1 — Layout shells

Shells wrap whole sections of the app. They provide the **outer frame** (header, sidebar, footer). Page content goes **inside** the shell.

### 3.1 Which shell to use

| Page type | App routes | Shell component | Path |
|-----------|------------|-----------------|------|
| Workspace (sidebar app) | `app/pages/(workspace)/**` | `DashboardShell` | `web-app/components/layout/dashboard-shell.tsx` |
| Marketing / public | `app/page.tsx`, some landing pages | `MarketingPageShell` | `web-app/components/layout/marketing-page-shell.tsx` |
| Auth (sign-in, register, …) | `app/pages/user/**` | `AuthPageLayout` | `web-app/pages-components/user/components/auth-page-layout.tsx` |
| Component template gallery | `app/pages/templates/**` | `MarketingPageShell` + `TemplatesPageLayout` | `web-app/pages-components/templates/components/` |

**Rule:** Do not mount sign-in or template demo pages inside `DashboardShell`. Use the correct shell from [web-app-pages.md](web-app-pages.md) section 3.

### 3.2 What each shell must handle (by viewport)

Designers and developers should agree on these behaviors **in the shell**, not per page.

#### DashboardShell (workspace)

| Viewport | Expected behavior |
|----------|---------------------|
| Smartphone | Sidebar hidden by default; open via **menu button** in a **drawer/sheet**; main content full width |
| Tablet | Same as smartphone, or narrow persistent sidebar if approved in design |
| Laptop | Persistent sidebar; collapsible width optional |
| Desktop | Persistent sidebar; wider main content area (`xl:max-w-7xl` on inner sections) |

#### MarketingPageShell (public pages)

| Viewport | Expected behavior |
|----------|---------------------|
| Smartphone | Compact header; primary nav in **hamburger menu** (sheet/drawer); logo + auth actions visible |
| Tablet | Increased horizontal padding; nav may stay in sheet or partially inline |
| Laptop / Desktop | Full horizontal nav row; trailing actions visible |

#### AuthPageLayout (sign-in, forgot password, …)

| Viewport | Expected behavior |
|----------|---------------------|
| Smartphone / Tablet | **Single column**: title, form card, footer links — centered |
| Laptop / Desktop | **Two columns**: marketing copy (`aside`) on the left, form on the right |

**Current code note:** `AuthPageLayout` already implements the two-column pattern with `lg:grid` and `hidden lg:flex` on the aside. Workspace and marketing shells should follow the same **shell-owned** pattern for mobile navigation.

### 3.3 Shell checklist (design + dev)

Before marking a shell change complete, verify:

- [ ] Navigation is reachable on **smartphone** (not hidden with no alternative).
- [ ] Touch targets on mobile are at least **44px** tall where possible (`h-11` buttons on forms).
- [ ] No horizontal scrolling on a **390px** wide viewport unless intentional (wide data tables need a scroll container).
- [ ] Focus order and keyboard access work with drawer open and closed.
- [ ] Theme uses **semantic tokens** only (`bg-background`, `text-foreground`, …) — see section 7.

---

## 4. Layer 2 — Layout primitives

Layout primitives are **small reusable components** that encode our breakpoint rules. They prevent every developer from rewriting the same Tailwind strings.

**Target location (as we adopt this kit):**

- `web-app/lib/responsive/` — breakpoint names and constants
- `web-app/components/layout/responsive/` — `PageSection`, `ResponsiveGrid`, etc.

Even before every primitive file exists, **follow the rules below** using the same class patterns.

### 4.1 PageSection (standard page width and padding)

Every page’s main content should sit inside a consistent horizontal container.

**Standard outer classes:**

```txt
mx-auto w-full max-w-6xl
px-4 py-8 sm:px-6 sm:py-10 md:py-12 lg:px-8 xl:max-w-7xl
```

**Meaning for juniors:**

| Class part | What it does |
|------------|--------------|
| `mx-auto` | Centers the block horizontally |
| `max-w-6xl` | Limits how wide content grows on laptop |
| `xl:max-w-7xl` | Allows slightly wider content on desktop |
| `px-4 sm:px-6 lg:px-8` | Increases side padding as the screen grows |

**Do not** repeat this full string on every page long term — wrap it in a `PageSection` component once the kit is added.

### 4.2 ResponsiveGrid (column presets)

Use **CSS grid** with responsive column counts. Avoid fixed pixel widths for columns.

| Preset name | Smartphone | Tablet | Laptop | Desktop |
|-------------|------------|--------|--------|---------|
| **cards** | 1 column | 2 columns (`sm:grid-cols-2`) | 2 columns | 3 columns (`xl:grid-cols-3`) |
| **split** | 1 column | 2 columns | 2 columns | 2 columns |
| **gallery** | 1 column | 2 columns | 2–3 columns | 3 columns |

**Example (cards preset):**

```tsx
<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
  {/* card items */}
</div>
```

This pattern is already used on the dashboard and template gallery index.

### 4.3 ShowFrom / HideFrom (visibility by viewport)

When a **block of UI** should only appear on some sizes (not a whole separate page), use show/hide utilities:

| Goal | Tailwind approach |
|------|-------------------|
| Show only on laptop and up | `hidden lg:flex` or `hidden lg:block` |
| Hide on laptop and up | `lg:hidden` |
| Show only on tablet and up | `hidden md:flex` |
| Hide below tablet | `hidden sm:block` patterns as needed |

**Example from auth:** marketing aside is `hidden` on phone/tablet and `lg:flex` on laptop+.

**Important:** Hiding content with CSS still keeps it in the DOM unless you use more advanced patterns. For heavy desktop-only widgets, ask a senior about lazy loading — but still use **one page component**.

### 4.4 Typography and spacing scales

Use responsive type steps instead of one fixed font size for all screens.

| Element | Example pattern |
|---------|-----------------|
| Page title | `text-2xl sm:text-3xl` or `text-2xl sm:text-3xl lg:text-4xl` |
| Body / supporting text | `text-sm sm:text-base` |
| Hero headline | `text-4xl sm:text-5xl lg:text-6xl` |
| Section vertical padding | `py-8 sm:py-10 md:py-12` |

**Designer rule:** Specify **min and max** type sizes in Figma per breakpoint range, not per device model.

**Developer rule:** Prefer **few steps** (2–3 per element). Too many breakpoints on one heading is hard to maintain.

### 4.5 Touch and form controls on mobile

From [web-app-pages.md](web-app-pages.md) section 4.3:

- Primary buttons on auth/forms: **`h-11`** on smartphone, optionally `sm:h-10` on larger screens.
- Every input needs a **`Label`** linked with `htmlFor` / `id`.
- Error text uses **`Alert`** with `role="alert"` and `aria-invalid` on fields.

---

## 5. Layer 3 — Page structure

This layer is where most juniors spend their time. The rules are strict and simple.

### 5.1 Folder layout (one page, one container)

```
pages-components/<area>/<page-name>/
  <page-name>-page.tsx           ← entry: renders container only
  components/
    page-container.tsx           ← all page UI and logic
    <optional-section>.tsx       ← large sections split for readability
```

**Example routes:** see [web-app-pages.md](web-app-pages.md) section 2.

### 5.2 Responsibilities by file

| File | Allowed | Not allowed |
|------|---------|-------------|
| `app/**/page.tsx` | Import and render `<XxxPage />` | Forms, hooks, layout, `components/ui` imports |
| `<page-name>-page.tsx` | Render `<XxxPageContainer />` | Business logic, big JSX trees |
| `page-container.tsx` | Page content, state, forms, composition | Reimplementing global header/sidebar/mobile nav |
| Section subcomponents | Focused UI chunks | Defining a second parallel page for another viewport |

### 5.3 How to build a new responsive page (step by step)

1. **Pick the shell** (section 3.1).
2. **Create** `page-container.tsx` inside the page folder.
3. **Wrap content** in `PageSection` (or the standard padding classes from section 4.1).
4. **Lay out lists of cards** with `ResponsiveGrid` / grid presets (section 4.2).
5. **Use** `ShowFrom` / `HideFrom` patterns only when two blocks swap (section 4.3) — not whole pages.
6. **Use** theme tokens and shadcn/ui components (section 7).
7. **Test** all four viewports (section 9).

### 5.4 When to split into subcomponents

Split `page-container.tsx` into sibling files under `components/` when:

- A section is **long** (roughly 80+ lines of JSX).
- A section is **reused** on the same page (form panel + success state).
- Different people will work on **independent sections**.

Do **not** split by viewport. Split by **feature or section** (`hero-section.tsx`, `sign-in-form.tsx`).

### 5.5 When two UI patterns are truly different (advanced)

Rarely, mobile and desktop need **different components** (bottom tab bar vs sidebar). Even then:

- Keep **one** `page-container.tsx`.
- Import **`MobileNav`** and **`DesktopNav`** as siblings.
- Render both; use `lg:hidden` and `hidden lg:flex` (or shell-level composition).

```tsx
// ✅ Good — two nav components, one page
<>
  <MobileNav className="lg:hidden" />
  <DesktopNav className="hidden lg:flex" />
  <PageContent />
</>

// ❌ Bad — four page containers by viewport
```

---

## 6. Breakpoints explained (Tailwind mobile-first)

### 6.1 How to read a responsive class

Take `sm:px-6`:

- **Below 640px:** only `px-4` (or whatever unprefixed padding you set) applies.
- **640px and above:** `px-6` applies.

Take `lg:grid lg:grid-cols-2`:

- **Below 1024px:** element stays a single column (no grid from `lg:` yet).
- **1024px and above:** grid with two columns.

### 6.2 Prefix quick reference

| Prefix | Min width | Our target name |
|--------|-----------|-----------------|
| *(none)* | 0px | Smartphone |
| `sm:` | 640px | Tablet (start) |
| `md:` | 768px | Tablet |
| `lg:` | 1024px | Laptop |
| `xl:` | 1280px | Desktop |
| `2xl:` | 1536px | Optional; use only when design requires extra width |

We mostly use **default, sm, md, lg, xl** — not every possible prefix on every element.

### 6.3 Common mistakes

| Mistake | Why it is wrong | Fix |
|---------|-----------------|-----|
| Desktop-first thinking (“remove columns on mobile”) | Tailwind is mobile-first | Start with one column; add columns at `sm:` / `xl:` |
| Separate page per device | Duplicated logic | One page + shells + grids |
| Hiding nav on mobile with no menu | Users cannot navigate | Add sheet/drawer in shell |
| Fixed `width: 400px` on cards | Breaks small phones | Use `w-full`, `max-w-*`, grid |
| Hard-coded colors | Breaks theme / dark mode | Use tokens from `globals.css` |

---

## 7. Visual design rules (EXL theme)

Responsive layout must still follow our visual system.

### 7.1 Semantic tokens only

Use classes like:

- `bg-background`, `text-foreground`, `text-muted-foreground`
- `border-border`, `bg-card`, `text-primary`
- `shadow-surface`

Do **not** paste hex colors or copy styling from other apps in the monorepo (`aspire.svc/`, MIDAS frontend, etc.) unless explicitly asked.

### 7.2 Components

Use **`web-app/components/ui/`** (shadcn/ui) for buttons, inputs, alerts, cards, etc. Add new primitives through `web-app/components.json` before building one-off controls.

### 7.3 Material Design principles (adapted to EXL)

We follow [Material Design](https://m3.material.io/) **structure**, not Google’s default purple colors:

- One **primary action** per screen.
- Clear order: **title → supporting text → content → actions**.
- Cards: rounded corners, border, subtle shadow (`rounded-xl`, `border-border`, `bg-card`, `shadow-surface`).

---

## 8. Enforcement — how we avoid gaps

“100% foolproof” needs **code conventions plus testing**. No approach eliminates all mistakes without a checklist.

### 8.1 Code conventions

| Rule | Owner |
|------|--------|
| Mobile nav and sidebar | Layout shells only |
| Page max-width and horizontal padding | `PageSection` / layout primitives |
| Grid column counts | `ResponsiveGrid` presets |
| Page-specific content | `page-container.tsx` only |
| Breakpoint constants documented | [web-design.md](web-design.md) + future `lib/responsive/breakpoints.ts` |

### 8.2 Designer handoff checklist

Before dev starts:

- [ ] Layouts sketched for all **four targets** (section 1.3).
- [ ] Mobile navigation pattern shown (menu → sheet).
- [ ] Primary button and touch target sizes noted for smartphone.
- [ ] Grids specified as **column counts per range**, not pixel widths.
- [ ] Tokens referenced (`primary`, `muted-foreground`, `card`, …) — not raw hex.

### 8.3 Developer done checklist

Before opening a PR:

- [ ] Correct **shell** used ([web-app-pages.md](web-app-pages.md) section 3).
- [ ] Thin route + **page-container** pattern ([web-app-pages.md](web-app-pages.md) section 2).
- [ ] No global nav/sidebar logic inside page container.
- [ ] Grids use responsive columns (section 4.2).
- [ ] Tested at **390px**, **768px**, **1280px**, **1440px** widths (section 9).
- [ ] `npm run build:fast` passes from `web-app/`.

### 8.4 Automated tests (recommended)

Add or extend Playwright (or similar) smoke tests at these viewports:

| Target | Width × height |
|--------|----------------|
| Smartphone | 390 × 844 |
| Tablet | 768 × 1024 |
| Laptop | 1280 × 800 |
| Desktop | 1440 × 900 |

Run at least one test per shell:

- `/` (marketing)
- `/pages/user/sign-in` (auth)
- `/pages/dashboard` (workspace)

Failures usually mean a **shell gap** (nav missing on mobile) or **horizontal overflow** on a page section.

---

## 9. Manual testing in the browser

You do not need every physical device. Use **browser DevTools device mode**.

### 9.1 Chrome / Edge steps

1. Open the page (local: `http://localhost:8811` + path).
2. Press **F12** → toggle **device toolbar** (phone/tablet icon).
3. Set widths: **390**, **768**, **1280**, **1440**.
4. Check:
   - Can you reach all navigation?
   - Does anything clip or scroll sideways?
   - Are buttons easy to tap on 390px width?
   - Does auth show two columns only at laptop width and above?

### 9.2 Pages to spot-check

| Page | Path |
|------|------|
| Marketing home | `/` |
| Sign in | `/pages/user/sign-in` |
| Dashboard | `/pages/dashboard` |
| Template gallery | `/pages/templates` |

---

## 10. Implementation roadmap (repo status)

Some gold-standard pieces are **documented here before every file exists**. Use this table to know what is live today vs planned.

| Piece | Status | Notes |
|-------|--------|-------|
| Four-target breakpoints in docs | **Live** | [web-app-pages.md](web-app-pages.md) section 5; this guide expands it |
| `AuthPageLayout` two-column at `lg:` | **Live** | `auth-page-layout.tsx` |
| Responsive grids on dashboard / templates | **Live** | `grid-cols-1 sm:grid-cols-2 xl:grid-cols-3` |
| `PageSection`, `ResponsiveGrid`, `ShowFrom` kit | **Planned** | Add under `components/layout/responsive/` |
| Mobile drawer for workspace sidebar | **Planned** | Requires shadcn `Sheet` in `DashboardShell` |
| Mobile menu for marketing header | **Planned** | `MarketingHeader` + sheet |
| Playwright four-viewport smoke tests | **Planned** | Section 8.4 |

When you implement a **planned** row, update this table in the same PR.

---

## 11. Quick reference card

**Remember:**

1. **One URL, one page-container** — not four pages per screen size.
2. **Shells own navigation** — sidebar, header, mobile drawer.
3. **Primitives own spacing and grids** — consistent padding and columns.
4. **Mobile-first Tailwind** — default = phone; add `sm:`, `lg:`, `xl:` as screens grow.
5. **Test four widths** — 390, 768, 1280, 1440.
6. **Theme tokens + shadcn/ui** — no ad-hoc colors or controls.

**Need page structure details?** → [web-app-pages.md](web-app-pages.md)

**Need colors and tokens?** → `web-app/app/globals.css`

---

## 12. FAQ

### Should we build a separate mobile site?

**No** for `web-app/`. One responsive app is our standard. A separate mobile site is only for products with deliberately different mobile UX and URLs.

### Should designers deliver four Figma frames?

**Yes for the four target ranges** (section 1.3). They do not need separate frames for every phone model.

### Can I use `useMediaQuery` in every page?

**Avoid it.** Prefer CSS/Tailwind. Use JavaScript media queries only in shells or rare cases (opening a drawer, loading a heavy chart on desktop). Too much JS breakpoint logic causes hydration bugs and duplicate paths.

### What if laptop and desktop look almost the same?

That is normal. Often the only difference is **`xl:max-w-7xl`** and **`xl:grid-cols-3`**. You still test both widths because small alignment bugs show up at the breakpoint boundary.

### Who approves breaking these rules?

Tech lead or senior front-end owner on **`web-app/`**. Exceptions must be documented in the PR description.
