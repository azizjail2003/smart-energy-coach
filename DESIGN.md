# Design

Calm, dense workspace for the FH Dortmund facilities team. Floating rounded cards and pills sit on a warm ground; FH Dortmund orange is the single working colour. The approved mockups still define the content and order of each page; this file describes how it is drawn.

## Principles

- Calm by default. Orange marks the brand, the current selection and the primary action. Warnings use the amber banner, not more orange.
- Every number shows its unit. Charts state their unit in the title and on the axis, and have a text summary and a data table.
- Floating surfaces. Cards, the rail, the building selector and menus are solid surfaces with a soft shadow on the ground colour. No borders around cards, no blur, no translucency, no gradients.
- One body face (IBM Plex Sans) for everything you read and click, with tabular numerals in data. Montserrat 700 for headings, the score, the error code and avatars only.
- The same screen in light and dark. Every colour is a token with a light and a dark value; components never use a literal colour.
- The same control looks the same on every page.

## Colour tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--brand` | `#F35C0B` | `#F6782F` | FH Dortmund orange: chart primary series, score value, meters, focus ring |
| `--primary` | `#C94A06` | `#F47A3A` | Filled buttons, active rail entry, selected tab underline |
| `--on-primary` | `#FFFFFF` | `#1F1209` | Text on `--primary` (4.7:1 light, 6.6:1 dark) |
| `--primary-ink` | `#B94100` | `#FF9C62` | Orange text: links, values above limit, selected filter |
| `--primary-tint` | `#FDEEE4` | `#3A2416` | Card title icons, advice strip, AI chat bubble |
| `--ground` | `#F2EFEB` | `#1A1816` | The canvas everything floats on |
| `--card` | `#FFFFFF` | `#252220` | Cards, pills, inputs |
| `--muted-bg` | `#F5F2EE` | `#2F2B28` | Hover, table header, user chat bubble, empty states |
| `--muted-bg-strong` | `#EBE7E1` | `#3A3531` | Segmented filter track, meter track |
| `--border` | `#E9E4DD` | white 8 % | Row hairlines, pill outline |
| `--input` | `#D8D2C9` | white 16 % | Input and secondary button outline |
| `--text` | `#2B2B2B` | `#ECE7E2` | Body text |
| `--muted` | `#6B655F` | `#A9A29A` | Secondary text (5.2:1 on `--ground`) |
| `--ok` / `--ok-tint` | `#1E7B3A` / `#E7F3EA` | `#6CC489` / `#1D2E22` | Improvements, online status, live dot |
| `--warn` / `--warn-tint` | `#8A4B00` / `#FFF3DC` | `#F2C063` / `#352A17` | Alert banner, fallback status |
| `--danger` | `#B42318` | `#F2877C` | Form errors, worse-than-before changes |
| `--chart-*` | | | Comparison series, lighting, servers, other, grid |

Brand orange `#F35C0B` has 3.3:1 contrast with white: enough for graphics and large text, not for small text. Small orange text and filled buttons use the darker tokens. In dark mode the primary is lifted and its text turns dark.

## Typography

IBM Plex Sans 400/500/600 and Montserrat 700 from Google Fonts, with system fallbacks.

| Role | Face / size / weight |
|---|---|
| Score value | Montserrat 46 / 700 |
| Error code | Montserrat 64 / 700 |
| KPI value | Plex 30 / 600 |
| Page title (top bar) | Montserrat 19 / 700 |
| Card title | Montserrat 15 / 700 (unit in Plex 13 / 400 after it) |
| Body, table cells, controls | Plex 14 / 400 |
| Secondary text, hints, table header | Plex 12.5–13 / 400–500 |

Sentence case everywhere; no all-caps labels.

## Layout

- **Shell:** a grid with the top bar across the full width, the rail column (88 px) beside the workspace, and a 32 px status bar. Only the workspace scrolls.
- **Top bar:** logo (wordmark on wide screens, mark below 1240 px; a light-letter copy in dark mode), page title with its one-line description, page tabs where a page has them (History periods), then the building selector and the report date as floating pills.
- **Rail:** two floating pills. Navigation at the top; at the bottom the hover-expansion switch, the theme switch (System → Dark → Light) and the team. Collapsed it is 56 px; hovering a pill or focusing a control with the keyboard widens it to 248 px over the page and the labels slide in. With expansion turned off the rail stays narrow and every entry has a tooltip. Both choices are kept in the browser.
- **Status bar:** live state on the left (green dot and "Live · score updated 15:05:10" on the dashboard, "Demo data" elsewhere), then university and team, time zone and version.
- **Dashboard:** alert banner; segmented category filter and four KPI cards (two by two) beside the score card; hourly chart (2/3) beside the device-type chart (1/3); AI coach strip.
- **History:** period tabs in the top bar; chart; alerts table; week-over-week table.
- **Scenarios, Coach, Settings:** two columns (form left, results or status right).
- **Phones (760 px and below):** normal page scroll; the rail becomes a floating bar at the bottom with the five pages and the theme switch; the status bar is hidden. At 390 px nothing overflows horizontally; wide tables scroll inside their own container.

## Spacing and shape

4 px grid; 16 px gaps between cards. Radius: cards 16 px, rail pills 28 px, inputs 8 px, text areas and inner blocks 12 px, buttons, chips, selects in the top bar and status pills fully round.

Shadows: `--shadow-float` for cards and pills on the ground; `--shadow-pop` (with a 1 px outline) for the rail and tooltips that sit over content.

## Components

- **Card:** `--card`, 16 px radius, `--shadow-float`, 20 px padding. Title row with the icon in a 34 px `--primary-tint` circle.
- **Button (primary):** `--primary`, `--on-primary` 600 text, 40 px, fully round, soft orange shadow; brightens on hover. Disabled at 55 % opacity.
- **Button (secondary):** `--card` with a 1 px `--input` outline.
- **Segmented filter:** muted track; the selected option sits on a raised card in `--primary-ink`.
- **Top bar tabs:** text links with a 2 px `--primary` underline on the selected one.
- **Inputs and selects:** `--card`, 1 px `--input`, 44 px, 8 px radius; focus turns the border `--primary` with a 3 px `--primary-tint` ring. Error state: `--danger` border and message below, linked with `aria-describedby`.
- **Tables:** no outer frame, `--muted-bg` header, hairlines between rows, row hover, tabular numerals.
- **Trend:** small filled triangle plus percentage; `--ok` when the change is an improvement, `--danger` when it is worse.
- **Status pill:** dot plus label; green for online, amber for fallback, neutral for cached.
- **Alert banner:** `--warn-tint` with an amber outline, warning icon on a white circle, round dismiss button.
- **Tooltip:** inverted (`--text` background, `--card` text), appears after 80 ms on hover or keyboard focus, hidden on phones.
- **Loading:** a muted block the size of the chart with "Loading chart…". **Error:** message plus a Retry button in the same place.

## Charts (Chart.js)

- Colours are read from the tokens each time a chart is drawn, and every chart is redrawn when the theme changes.
- Line: primary series `--brand`, 2 px; comparison `--chart-compare`, dashed; limit line dashed, labelled in the legend. Points above the limit are drawn larger in `--primary-ink`. Fewer time labels on phones.
- Bar: device types use their category colours; the selected category keeps full colour and the others fade.
- Axis titles show the unit. Legend at the bottom with line-style markers. Animations off when `prefers-reduced-motion: reduce`.

## Focus and motion

Visible focus ring: 2 px `--brand` outline with 2 px offset on every interactive element. Motion: 150 ms colour transitions, the 200 ms rail width change with labels following it, and 80 ms tooltip fades. All of it is removed under `prefers-reduced-motion`.

## Decisions

- The shell, floating surfaces, rail behaviour, tooltips and status bar follow the JPTRACK dashboard kit; the colours stay FH Dortmund orange instead of the kit's purple, and the fonts follow the kit (IBM Plex Sans, Montserrat).
- Labels stay visible in content (filters, buttons, table headers). Only the rail relies on icons, because its labels appear on hover.
- The dark-mode logo is a copy of the logo with the dark letters and building recoloured to the dark text colour; the orange and green are unchanged.
