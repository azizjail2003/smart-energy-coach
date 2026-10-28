# Design

Swiss-style internal operations interface for the FH Dortmund facilities team. The approved mockups define layout, density and hierarchy for all five pages. Data comes first; decoration is limited to what explains the data.

## Principles

- Calm by default. Orange marks the brand, the current selection and the primary action. Warnings use the amber banner, not more orange.
- Every number shows its unit. Charts state their unit in the title and on the axis, and have a text summary and a data table.
- Square-ish surfaces with 1 px borders and no shadows. Hierarchy comes from type size and weight, not from boxes inside boxes.
- One family (Fira Sans) for everything, with tabular numerals in data.
- The same control looks the same on every page.

## Colour tokens

| Token | Value | Use |
|---|---|---|
| `--orange` | `#F35C0B` | FH Dortmund orange: logo, active nav marker, chart primary series, score value, focus ring |
| `--orange-strong` | `#C94A06` | Filled buttons and selected chips (white text 4.7:1) |
| `--orange-ink` | `#B94100` | Orange text on white or tint (5.5:1): active nav label, values above limit, links |
| `--orange-tint` | `#FDEFE6` | Active nav background, coach answer, advice strip |
| `--bg` | `#FAFAF8` | Page background |
| `--surface` | `#FFFFFF` | Cards, inputs, tables |
| `--surface-muted` | `#F3F2EE` | Table headers, user chat message, neutral pill |
| `--border` | `#E3E1DC` | Card and table borders |
| `--border-strong` | `#CFCCC5` | Inputs and secondary buttons |
| `--text` | `#2B2B2B` | Body text |
| `--muted` | `#6B6862` | Secondary text (5.3:1 on `--bg`) |
| `--green` | `#1E7B3A` | Improvements (lower use, higher score), online status |
| `--green-tint` | `#E9F4EC` | Success messages, scenario summary |
| `--amber-tint` | `#FFF4E0` | Alert banner background |
| `--amber-border` | `#F2C97D` | Alert banner border |
| `--amber-ink` | `#8A4B00` | Fallback status text |
| `--red` | `#B42318` | Form errors, worse-than-before changes |
| `--chart-compare` | `#85837E` | Comparison series (dashed) and limit line |
| `--chart-lighting` | `#F8A06B` | Lighting bar |
| `--chart-servers` | `#6B6862` | Servers bar |
| `--chart-other` | `#C9C6BF` | Other bar |

Brand orange `#F35C0B` has a 3.3:1 contrast with white, which is enough for large text and graphics but not for small text. Small orange text and white-on-orange buttons use the darker tokens above.

## Typography

Fira Sans 400/500/600/700 from Google Fonts, falling back to `system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif`. Fixed rem scale, ratio about 1.2.

| Role | Size / weight |
|---|---|
| Score value | 44px / 700 |
| KPI value | 34px / 600 |
| Page title | 26px / 600 |
| Card title | 17px / 600 (unit in 400 after it) |
| Body, table cells, controls | 15px / 400 |
| Secondary text | 13px / 400 |
| Sidebar footer, captions | 12px / 400 |

Numbers in KPIs, tables and charts use `font-variant-numeric: tabular-nums`. Sentence case everywhere; no all-caps labels.

## Layout

- Sidebar 232 px: logo, five nav items with 20 px line icons, footer (university, team, "Demo data").
- Header row: page title (and one-line description where the mockup has one), building selector, report date.
- Content: 12-column-free CSS grid per page, 16 px gaps, 24 px page padding.
- Dashboard: alert banner; category chips + four KPI cards beside the score card; hourly chart (2/3) beside the device-type chart (1/3); AI coach strip.
- History: period buttons; chart; alerts table; week-over-week table.
- Scenarios, Coach, Settings: two columns (form left, results/status right).
- Below 960 px the sidebar becomes a top bar with a menu button; columns stack. At 375 px nothing overflows horizontally; wide tables scroll inside their own container.

## Spacing and shape

Spacing steps 4, 8, 12, 16, 20, 24, 32 px. Radius 4 px for cards, inputs, buttons and chips; status pills are fully rounded. Borders 1 px. No shadows, gradients or decorative imagery.

## Components

- **Card:** white, 1 px `--border`, 4 px radius, 20 px padding, title row with a 20 px icon.
- **Button (primary):** `--orange-strong`, white 600 text, 40 px high. Hover darkens to `--orange-ink`. Disabled at 55 % opacity.
- **Button (secondary) and chips:** white, 1 px `--border-strong`. Selected chip uses the primary style.
- **Inputs and selects:** white, 1 px `--border-strong`, 40 px high. Error state: `--red` border and message below, linked with `aria-describedby`.
- **Tables:** `--surface-muted` header row, 1 px row and column dividers, left-aligned values with tabular numerals (as in the mockups). Wide tables scroll inside their own container.
- **Trend:** small filled triangle icon plus percentage; green when the change is an improvement, red when it is worse.
- **Status pill:** dot plus label; green for online, amber for fallback, neutral for cached.
- **Alert banner:** amber tint, 1 px amber border, warning icon, dismiss button.
- **Loading:** a muted block the size of the chart with "Loading chart…". **Error:** message plus a Retry button in the same place.

## Charts (Chart.js)

- Line: primary series `--orange`, 2 px, 3 px points; comparison `--chart-compare`, dashed; limit line `--chart-compare`, dashed, labelled in the legend. Points above the limit are drawn larger in `--orange-ink`.
- Bar: device types use their category colours; the selected category keeps full colour and the others fade.
- Axis titles show the unit. Legend at the bottom with line-style markers. Animations off when `prefers-reduced-motion: reduce`.

## Focus and motion

Visible focus ring: 2 px `--orange` outline with 2 px offset on every interactive element. Motion is limited to 150 ms colour transitions on controls and is removed under `prefers-reduced-motion`.
