# Design System Document: The Editorial Intelligence

## 1. Overview & Creative North Star

### Creative North Star: "The Digital Curator"
This design system is not a dashboard; it is an authoritative publication. It eschews the frantic, "tech-first" aesthetics of traditional fintech for the measured, high-trust environment of a legacy financial journal. By treating data as editorial content, we elevate the user from a mere observer to an informed strategist.

**The Aesthetic Blueprint:**
The system breaks the "template" look through **intentional asymmetry** and **high-contrast typography scales**. We move away from the rigid, boxed-in grids of SaaS products, instead using generous "white space" (parchment space) and overlapping layers to create a sense of tactile depth. The goal is a visual experience that feels curated, not generated.

---

## 2. Colors

The palette is anchored in heritage and prestige. We utilize a "Parchment and Ink" foundation to provide immediate visual comfort during long-duration analysis.

### Color Tokens
*   **Primary (The Ink):** `#040D17` – An almost-black navy used for authoritative headings and high-priority CTAs.
*   **Background (The Paper):** `#FDF9EE` – A soft parchment that reduces eye strain compared to pure white.
*   **Surface Tiers:**
    *   `surface_container_lowest`: `#FFFFFF` (Used for "floating" active cards)
    *   `surface_container_low`: `#F7F3E8`
    *   `surface_container_highest`: `#E6E2D8` (Used for deep nesting or secondary sidebars)

### The "No-Line" Rule
To maintain an editorial feel, **prohibit 1px solid borders for sectioning.** Structural boundaries must be defined solely through background color shifts. A section should be distinguished from the main background by transitioning from `surface` to `surface-container-low`.

### The Glass & Gradient Rule
For elements that require high prominence (e.g., floating action bars or premium insight modals), use **Glassmorphism**.
*   **Effect:** Apply `surface_container_low` at 80% opacity with a `24px` backdrop-blur. 
*   **Signature Texture:** Main CTAs should use a subtle vertical gradient from `primary` (`#040D17`) to `primary_container` (`#1A232E`) to provide a "pressed ink" depth that flat colors lacks.

---

## 3. Typography

Typography is the primary vehicle for the brand’s "Expert" tone. We pair a high-character Serif with a utilitarian Sans-serif.

*   **Display & Headlines (Newsreader):** Used for all storytelling elements. The serif's varying stroke weights convey a "Wall Street Journal" legacy. Use `display-lg` (3.5rem) for hero stats and `headline-md` (1.75rem) for section titles.
*   **UI & Data (Work Sans):** Used for numbers, labels, and interactive elements. The clean, geometric nature of Work Sans ensures that complex financial data remains legible at small sizes (e.g., `label-sm` at 0.6875rem).

**Editorial Hierarchy:**
Every page should have a clear "Front Page" hierarchy. Use `display-md` for the primary insight of the page, ensuring it has enough breathing room (using Spacing Scale `16` or `20`) to command attention.

---

## 4. Elevation & Depth

We convey hierarchy through **Tonal Layering** rather than structural lines or heavy shadows.

*   **The Layering Principle:** Depth is achieved by "stacking" surface tiers. Place a `surface-container-lowest` card on a `surface-container-low` section to create a soft, natural lift.
*   **Ambient Shadows:** If a floating element is required, use "Ink Shadows." Shadows must be extra-diffused: 
    *   *Values:* `0px 12px 32px`
    *   *Color:* `on_surface` (`#1C1C15`) at **4% opacity**. This mimics the way natural light hits heavy paper.
*   **The Ghost Border Fallback:** If a border is required for accessibility in data tables, use `outline-variant` at **15% opacity**. Never use 100% opaque borders.

---

## 5. Components

### Buttons
*   **Primary:** Solid `primary` background with `on_primary` text. `0.25rem` (DEFAULT) roundedness. 
*   **Secondary:** Ghost style. No background, `primary` text, and a `Ghost Border` (15% opacity `outline`).
*   **State:** On hover, primary buttons should shift to a subtle gradient; secondary buttons should fill with `surface_container_high`.

### Minimalist Cards
Cards must not have visible borders. They are defined by a shift to `surface_container_lowest`. 
*   **Padding:** Always use at least `Spacing 6` (2rem) for internal card padding to maintain the editorial feel.
*   **Data Lists:** Forbid divider lines. Separate list items using `Spacing 3` (1rem) of vertical white space and a subtle `surface_container_low` hover state.

### Input Fields
*   **Visual Style:** Underlined or "Soft Box." Avoid heavy outlines. Use `surface_container_low` as the field background with a `2px` bottom border in `primary` only when focused.
*   **Typography:** Labels use `label-md` in `on_surface_variant`.

### Financial Data Visualization
*   **The "Ticker" Component:** Use `newsreader` for the primary value (e.g., stock price) and `workSans` for the percentage change.
*   **Color Logic:** Success/Positive data should use a darkened version of standard green to match the navy's weight; Error/Negative data uses `error` (`#BA1A1A`).

---

## 6. Do's and Don'ts

### Do
*   **DO** use asymmetric layouts. If a chart is on the left, let the right-side text breathe with uneven margins.
*   **DO** use "Surface Nesting" to group related financial metrics.
*   **DO** treat data as prose. Lead with a headline, follow with the data "body."

### Don't
*   **DON'T** use 1px solid black borders. It breaks the sophisticated, "organic paper" feel.
*   **DON'T** use standard "Material Design" shadows. They feel too "app-like" and not "editorial."
*   **DON'T** crowd the interface. If the data is important, give it a full `Spacing 12` (4rem) block of isolation.
*   **DON'T** use bright, vibrant primary blues. Stick to the Deep Navy (`#1A232E`) to maintain the "Modern-Classic" persona.

---

## 7. Spacing Scale

Strict adherence to the spacing scale maintains the rhythmic "scanning" experience of a newspaper.
*   **Micro-spacing (0.5 - 2):** For internal component alignment (e.g., icon to text).
*   **Section Spacing (8 - 16):** For separating distinct editorial modules.
*   **Gutter Spacing (4):** The standard margin for grid-based data layouts.