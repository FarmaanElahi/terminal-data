# Design System

This document defines the design philosophy, visual language, and interaction patterns for the terminal UI. All frontend work must follow these guidelines to maintain consistency.

## Philosophy

The UI is inspired by professional trading terminals (Bloomberg, Reuters). It prioritizes **information density over decoration**. The interface should feel precise, fast, and trustworthy — not consumer-grade.

Core principles:
- **Data first**: Every pixel should serve the data. Decorative elements are kept to a minimum.
- **Dark by default**: Dark mode is the primary experience. Light mode is a supported alternative.
- **Monochromatic with intent**: Color is used functionally (up/down, primary action, warning) — never decoratively.
- **No noise**: No gradients, no shadows except where structurally necessary, no rounded corners that make things feel "soft".

---

## Color System

Uses OKLCH color space for perceptually uniform colors across themes.

### Dark Mode (Primary)

| Token | Value | Usage |
|---|---|---|
| `--background` | `oklch(0.13 0.01 250)` | Page background |
| `--foreground` | `oklch(0.93 0.01 250)` | Primary text |
| `--card` | `oklch(0.17 0.01 250)` | Panel/card backgrounds |
| `--border` | `oklch(0.28 0.01 250)` | Borders and dividers |
| `--muted` | `oklch(0.22 0.01 250)` | Subtle backgrounds (hover states, inputs) |
| `--muted-foreground` | `oklch(0.6 0.01 250)` | Secondary text |
| `--primary` | `oklch(0.65 0.2 250)` | Primary action, links, active states |
| `--primary-foreground` | `oklch(0.98 0 0)` | Text on primary backgrounds |
| `--destructive` | `oklch(0.6 0.2 25)` | Errors, negative values |
| `--success` | `oklch(0.65 0.2 150)` | Positive values, gains |
| `--warning` | `oklch(0.75 0.15 75)` | Warnings, neutral-to-negative signals |

### Light Mode

| Token | Value | Usage |
|---|---|---|
| `--background` | `oklch(0.96 0.005 250)` | Page background |
| `--foreground` | `oklch(0.15 0.01 250)` | Primary text |
| `--card` | `oklch(1 0 0)` | Panel/card backgrounds |
| `--border` | `oklch(0.82 0.005 250)` | Borders |
| `--primary` | `oklch(0.55 0.22 250)` | Primary action |

### Financial Color Conventions

Always use these semantic tokens — never raw colors — for financial data:
- **Gain / Up / Positive**: `text-[oklch(0.65_0.2_150)]` or the `--success` token
- **Loss / Down / Negative**: `text-destructive` or the `--destructive` token
- **Neutral**: `text-muted-foreground`

---

## Typography

### Fonts

| Role | Font | Weights |
|---|---|---|
| UI / Body | Inter | 300, 400, 500, 600, 700 |
| Code / Symbols / Numbers | JetBrains Mono | 400, 500 |

Both fonts are loaded from Google Fonts with `font-display: swap`.

### Rules

- **Financial numbers always use tabular numerals** — use the `.font-tabular` utility class or the `font-variant-numeric: tabular-nums` CSS property. This ensures columns of numbers align correctly.
- **Ticker symbols** should use `font-mono` (JetBrains Mono).
- **Formulas and expressions** use `font-mono`.
- **UI labels, buttons, headings** use Inter (default sans).
- Prefer `text-sm` (14px) as the base body size. Use `text-xs` (12px) for dense data tables.

### Scale

| Class | Size | Usage |
|---|---|---|
| `text-xs` | 12px | Table cells, badges, dense labels |
| `text-sm` | 14px | Default body, inputs, buttons |
| `text-base` | 16px | Larger body copy |
| `text-lg` | 18px | Dialog titles |
| `text-xl`+ | 20px+ | Page headings (use sparingly) |

---

## Border Radius

The base radius is **4px** — deliberately tight. This signals precision over softness.

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | ~0px | Almost sharp (e.g., small badges) |
| `--radius-md` | 2px | Inline elements |
| `--radius` (base) | 4px | Inputs, buttons, cards, panels |
| `--radius-lg` | 4px | Same as base |
| `--radius-xl` | 8px | Larger containers, dialogs |

Never use large radius values (16px+) on functional UI components. Reserve softer radius only for decorative or marketing-oriented elements if they ever appear.

---

## Spacing

Base unit: **4px** (Tailwind default).

Consistent spacing conventions:
- **Table row height**: 28px (`h-7`)
- **Compact controls** (buttons, inputs in toolbars): `h-7` or `h-8`
- **Standard controls** (form inputs): `h-9`
- **Panel padding**: `p-2` to `p-3` (8–12px)
- **Section gaps**: `gap-2` to `gap-4`
- **Dialog padding**: `p-6`
- **Header height**: `h-8` (32px)

Use tight spacing. Avoid padding that wastes screen real estate. Every row visible in a data table is valuable.

---

## Animations & Interactions

### Principles
- Animations should be **functional, not decorative**. They communicate state changes.
- Keep durations short: `150ms`–`300ms` for transitions, `600ms` max for cell flashes.
- No bounce, spring, or overshoot. Ease-out is the default easing.

### Standard Transitions

| Interaction | Pattern |
|---|---|
| Hover color change | `transition-colors duration-150` |
| Panel open/close | `animate-in fade-in-0 zoom-in-95 duration-200` |
| Dropdown/popover | `animate-in fade-in-0 slide-in-from-top-2 duration-150` |
| Dialog | `animate-in fade-in-0 zoom-in-95 duration-200` |

### Cell Flash (Real-time Data Updates)

When a value changes in a data table, use the `.cell-flash-up` or `.cell-flash-down` CSS class:

```css
.cell-flash-up   /* green highlight, 0.6s ease-out */
.cell-flash-down /* red highlight, 0.6s ease-out */
```

Pair with a brief `scale-110 brightness-125` on the element during the flash for added emphasis.

### Focus Rings

All interactive elements must have visible focus rings for keyboard navigation:
```
focus-visible:ring-ring/50 focus-visible:ring-[3px]
```

This is already baked into all shadcn/ui components. Do not disable or override focus-visible styles.

---

## Component Conventions

### Shadcn/ui

All basic UI primitives come from shadcn/ui. Never reinvent buttons, inputs, dialogs, selects, tooltips — use the existing components in `src/web/src/components/ui/`.

**Available components**: Button, Card, Input, Badge, Dialog, Select, Tooltip, Tabs, DropdownMenu, Sheet, ScrollArea, Label, Command, ContextMenu, Separator, Table, Sonner (toast).

### Button Variants

| Variant | Usage |
|---|---|
| `default` | Primary action |
| `outline` | Secondary action |
| `ghost` | Toolbar/icon buttons, low-emphasis actions |
| `destructive` | Delete, danger actions |
| `secondary` | Alternative action |
| `link` | Text-link behavior |

Icon-only buttons: use `size="icon"`, `size="icon-sm"`, or `size="icon-xs"`.

### Icons

Use **Lucide React** exclusively. Do not introduce other icon libraries.

```tsx
import { ChevronDown, Settings, Plus } from "lucide-react"
```

Default icon sizes:
- In buttons: match button size (e.g., `h-4 w-4` for standard, `h-3.5 w-3.5` for small)
- Standalone: `h-4 w-4`

### Cards / Panels

All panels use `bg-card border border-border`. No shadow by default — borders define structure.

### Scrollbars

- Data-heavy containers: `.scrollbar-thin` (6px, muted color)
- UI chrome (tab bars etc.): `.scrollbar-none` (hidden)
- Never use browser default scrollbars in key UI areas

---

## Layout

### Header

Fixed at `h-8` (32px). Contains logo, layout tabs, and right-side controls. Uses `bg-card border-b`. The header must remain minimal — no additional elements without strong justification.

### Dashboard

The main content area is a drag-and-drop grid of panes (`react-dnd`). Each pane hosts exactly one widget. Panes can be split, resized, maximized (fullscreen overlay), or floated.

### Dialogs

- Overlay: `bg-black/50` backdrop
- Max width: `sm:max-w-lg` on desktop, `max-w-[calc(100%-2rem)]` on mobile
- Always use `DialogHeader`, `DialogTitle`, `DialogDescription` for accessibility

---

## Dark Mode Implementation

Dark mode is implemented via the `.dark` class on `<html>`. All colors are CSS custom properties that switch based on this class. Do not use hardcoded color values — always use tokens (`bg-background`, `text-foreground`, `border-border`, etc.).

```tsx
// Correct
<div className="bg-card text-foreground border-border">

// Wrong
<div className="bg-zinc-900 text-white border-zinc-700">
```

Access current theme in components:
```tsx
const theme = useLayoutStore((s) => s.theme)
const isDark = theme === "dark"
```

---

## What Not To Do

- No gradients on functional UI (cards, buttons, panels)
- No large rounded corners (>8px) on data components
- No shadows on cards/panels — use borders instead
- No animations over 400ms for UI transitions
- No raw color values — always use CSS tokens
- No new icon libraries — Lucide only
- No inline styles for layout/spacing — use Tailwind utilities
- No decorative empty states with illustrations — keep it minimal and text-based
- Do not use `text-green-500` or `text-red-500` directly — use the semantic `--success` / `--destructive` tokens
