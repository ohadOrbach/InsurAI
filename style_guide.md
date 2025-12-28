# Application Style Guide: Modern Insurtech (Apple-Inspired)

## 1. Design Philosophy
**Core Pillars:** `Clarity`, `Trust`, `Fluidity`.
This application follows the **Apple Human Interface Guidelines (HIG)** adapted for Insurance Technology.
* **Minimalism:** Content comes before chrome. Use whitespace to reduce cognitive load.
* **Trust:** Use deep, stable colors for data and vibrant, clear colors for actions.
* **Depth:** Use subtle shadows, blurring (glassmorphism), and layering to establish hierarchy.
* **Feedback:** Every interaction must feel responsive and tactile.

---

## 2. Color Palette
We use a **Semantic Color System**. Do not use raw hex codes in code; use the semantic variable names (e.g., `bg-surface-primary`).

### 2.1. Brand & Action (Trust & Tech)
* **Primary Action (Apple Blue):** `#0071E3` (Tailwind: `blue-600`)
    * *Usage:* Primary buttons, active states, links.
* **Primary Hover:** `#0077ED` (Tailwind: `blue-500`)
* **Secondary/Brand (Deep Navy):** `#1D1D1F` (Tailwind: `slate-900`)
    * *Usage:* Headings, strong brand elements, "Dark Mode" surfaces.

### 2.2. Functional / Status (Insurance Context)
* **Success / Covered (Mint Green):** `#34C759` (Tailwind: `emerald-500`)
    * *Usage:* "Policy Active", "Payment Successful", Positive trends.
* **Warning / Attention (Warm Amber):** `#FF9500` (Tailwind: `amber-500`)
    * *Usage:* "Renewal Due", "Action Required", Pending states.
* **Critical / Uncovered (Soft Red):** `#FF3B30` (Tailwind: `rose-500`)
    * *Usage:* "Payment Failed", "Policy Expired", Destructive actions.

### 2.3. Backgrounds & Surfaces (The "Apple" Look)
* **App Background:** `#F5F5F7` (Off-White/Light Gray)
    * *Note:* Never use pure white `#FFFFFF` for the main background.
* **Surface Primary (Cards/Modals):** `#FFFFFF` (Pure White)
* **Surface Secondary (Inputs/Grouped lists):** `#F2F2F7` (System Gray 6)
* **Glassmorphism (Blur):** `rgba(255, 255, 255, 0.72)` with `backdrop-filter: blur(20px)`

---

## 3. Typography
**Font Family:** `Inter` or `SF Pro Display`.
* **Headings:** Tight tracking (`-0.02em`), Heavy/Bold weight.
* **Body:** Normal tracking, Regular/Medium weight. High readability is crucial for insurance policies.

| Role | Size (Desktop/Mobile) | Weight | Tracking | Color |
| :--- | :--- | :--- | :--- | :--- |
| **H1 (Page Title)** | 32px / 28px | Bold (700) | -0.02em | `text-slate-900` |
| **H2 (Section)** | 24px / 20px | Semibold (600) | -0.01em | `text-slate-900` |
| **H3 (Card Title)** | 18px / 18px | Medium (500) | Normal | `text-slate-800` |
| **Body (Policy Text)** | 16px / 16px | Regular (400) | Normal | `text-slate-600` |
| **Caption/Label** | 13px / 13px | Medium (500) | +0.01em | `text-slate-500` |

---

## 4. UI Components & Shapes

### 4.1. Cards & Containers (The "Island" Concept)
* **Border Radius:** `20px` (Large, smooth curves).
* **Shadow:** Large, diffuse, soft shadow.
    * *CSS:* `box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);`
* **Border:** Subtle 1px border for contrast.
    * *CSS:* `border: 1px solid rgba(0, 0, 0, 0.05);`

### 4.2. Buttons
* **Primary:** Pill-shaped (Full rounded).
    * *Height:* `48px` (Touch target compliant).
    * *Text:* White, Semibold.
    * *Mobile:* Full width (`w-full`).
* **Secondary:** Light gray background (`#F2F2F7`) with Primary Blue text.
* **Ghost:** Text only, Primary Blue.

### 4.3. Forms (Crucial for Insurance)
* **Inputs:** High height (`50px`), rounded corners (`12px`).
* **Background:** Light Gray (`#F2F2F7`) initially, White on focus.
* **Focus State:** 2px ring of Primary Blue (`ring-2 ring-blue-500`).
* **Labels:** Always visible, placed above input (or floating).

---

## 5. Layout & Spacing
**Grid System:** 8pt Grid. All spacing/sizing should be divisible by 4 or 8.

* **Padding (Container):**
    * *Mobile:* `16px` (Tailwind `p-4`)
    * *Desktop:* `32px` or `48px` (Tailwind `p-8` or `p-12`)
* **Gap (Between Elements):**
    * *Tight:* `8px` (Related items)
    * *Normal:* `16px` (Form fields, list items)
    * *Loose:* `32px` (Sections)

---

## 6. Implementation Rules (for AI)
**When generating code, follow these strict rules:**

1.  **Tailwind CSS First:** Use Tailwind utility classes for all styling.
2.  **Lucide React Icons:** Use `lucide-react` for icons. Stroke width: `2px`. Color: `text-slate-500` (default) or `text-blue-600` (active).
3.  **Mobile First:** Write classes for mobile first, then `md:` or `lg:` for desktop.
4.  **Accessibility (WCAG AA):**
    * Ensure text contrast ratio is > 4.5:1.
    * All interactive elements must have `aria-label` if no text is present.
    * Focus rings must be visible on all inputs/buttons.
5.  **Clean Code:** Do not use inline styles. Use `clsx` or `tailwind-merge` for dynamic classes.

### Example Component (Tailwind + React)
```tsx
export function PolicyCard({ title, amount, status }: PolicyProps) {
  return (
    <div className="bg-white rounded-[20px] p-6 shadow-sm border border-slate-100 hover:shadow-md transition-all duration-300">
      <div className="flex justify-between items-start mb-4">
        <div>
           <h3 className="text-lg font-medium text-slate-900">{title}</h3>
           <p className="text-sm text-slate-500 mt-1">Monthly Premium</p>
        </div>
        <span className={clsx(
          "px-3 py-1 rounded-full text-xs font-semibold",
          status === 'active' ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-500"
        )}>
          {status === 'active' ? 'Covered' : 'Inactive'}
        </span>
      </div>
      <div className="text-3xl font-bold text-slate-900 tracking-tight">
        {amount}
      </div>
    </div>
  );
}
