# Frontend refactor handoff: Figma redesign + dark/light themes

Written 18/11/2026 for the next model. The owner (Vietnamese speaker, replies in Vietnamese) approved the plan and the visual demo. Phases 1-2 are committed (`df6017b`). **Phases 3-6 were done later the same day and are NOT committed yet; see §8 for what changed and what is left.** Sections 4-5 below describe the state BEFORE phases 3-6 (kept as the record of the plan).

## 0. Start here

- Branch: `refactor-fe` (git does not allow spaces, so not "refactor FE"). Commit `df6017b` holds Phases 1-2. Base: `feat/tk49-answer-actions` @ `45f12b4`.
- Working dir: `frontend/` (React 18 + Vite + Tailwind v4 + react-router, no test runner).
- **Never touch or stage `backend/`.** Four backend files (`orchestrator.py`, `focus.py`, `test_conversation_focus.py`, `test_input_policy.py`) show as modified in `git status`: they belong to another session. Stage frontend paths explicitly (`git add frontend/...`), never `git add -A`.
- Do not commit or push unless the owner says so. Commit messages end with the attribution line the harness asks for.
- Report to the owner after each phase and wait for a go before the next one. Explain in plain words (what changed, why, what you did not check); the owner dislikes jargon and abbreviations.
- Every fix must work for English AND Vietnamese (`src/locales/en.ts`, `vi.ts`, `types.ts`). New visible text goes into the three locale files, never hard-coded in TSX.
- Docs/comments in the repo are mixed English/Vietnamese; write new comments in English.

## 1. The design (Figma)

File key `PIS0a09i3Gf2fg9wKGpdb1`, one page, three frames, all 1440 wide:

| Frame | Node | Link |
|---|---|---|
| 01 · FinHelp — Homepage (1440×2808) | `2:2` | https://www.figma.com/design/PIS0a09i3Gf2fg9wKGpdb1/Untitled?node-id=2-2&m=dev&t=XBJjImLnNnORAySR-1 |
| 02 · Workspace — Start analysis (1440×1024) | `2:11` | https://www.figma.com/design/PIS0a09i3Gf2fg9wKGpdb1/Untitled?node-id=2-11 |
| 03 · Workspace — Answer and sources (1440×1024) | `2:15` | https://www.figma.com/proto/PIS0a09i3Gf2fg9wKGpdb1/Untitled?node-id=2-15&t=H9CqfSb94jLkWJQl-1&scaling=min-zoom&content-scaling=fixed&page-id=0%3A1 |

Read them with the Figma MCP: `create_session` (fileKey above) → `get_screenshot` (nodeId `2:2` / `2:11` / `2:15`, `maxDimension` up to 2808) or `get_metadata` for the layer tree with sizes. The file has no variables (`get_variable_defs` returns `{}`), so colours below were sampled from screenshots.

**Offline copy of the whole design as a clickable page:** open `frontend/design-handoff/ui_demo_v2.html` in a browser. Tabs: 01 Homepage, 02 Start analysis, 03 Answer + sources, 04 Sign in / register / reset (no Figma frame: invented in the same style from the real forms). Buttons on top: Dark/Light switch, and "Hiện chú thích" which shows numbered markers (H1-H9, S1-S5, A1-A8) matching the gap tables below. The demo is desktop-width only (1440). Treat it as the visual spec, not as code to paste.

### The Figma is the LIGHT theme. Dark keeps today's palette.

Light values (final ones live in `src/index.css`, blocks `[data-theme="light"]`): page `#f6f7fb`, cards/white `#ffffff`, borders `#e5e9f2`, text `#111c32`, muted `#5b6579`, accent `#3659e3`, accent soft `#edf1ff`, CTA band `#edf1ff`, **navy sidebar `#111c32`** (active item `#22314f`, guest card `#1b2a46`), trust band `#111c32`. The sidebar and the trust band stay navy in BOTH themes (tokens `--side-*`, `--band-*`).

### Measurements from the Figma metadata

- **Workspace shell (02 and 03):** sidebar 232 wide; header 80 tall (breadcrumb "Workspace › title", left padding 32); content below.
- **03 Answer:** conversation column 760 wide (scope bar 72 tall; padding 28; user label "YOU" then user box 704×73 radius ~12; answer card 704 wide, padding 20, radius 16; comparison table 664 wide, header 39 tall, rows 55 tall; two source cards 324×76 with 16 gap; "Copy answer / Report an issue / Illustrative answer" row; follow-up suggestion chip 368×29; composer 704×76 (placeholder, "+ 2 reports in scope", round send button 36); hint row "Enter to send · Shift + Enter for a new line" left and "Check important figures against the source." right). Source viewer 448 wide: header 72 ("Source preview", "All reports (2) ⌄" select, close), file block (name, "Sample filing · Annual report", open-external icon, page row: prev, page box "45", "/ 64", next, "100%", fullscreen), citation context bar 43 ("1  Income statement · Highlighted in source"), paper page 408×568 (revenue row highlighted with a 3px left edge), explanation card "Read the context, not just the number. Citations open the matching page and passage."
- **02 Start analysis:** content column 900 wide, left-aligned at x=154; eyebrow "LESS SEARCHING. MORE UNDERSTANDING."; h1 "Your next insight starts with a report." (≈36px); subtitle; 3-step bar (1 Add a report / 2 Ask a question / 3 Verify the source, step 1 active); upload card 900×284 holding a dashed drop zone 860×244 (icon tile 56, "Drop your financial report here", "Annual reports, Form 10-K and financial statements", button "Choose PDF", "PDF only · Up to 5 MB · 1 report in guest mode"); line "Documents are isolated to this session." + link "Want to explore first? Try a demo →"; section "A few good questions to start with" with three 284×158 cards (Compare performance / Understand cash flow / Read between the lines, gap 24); footer line "Answers are grounded in your selected reports — not investment advice."; header right shows "Session-only · Not saved".
- **01 Homepage:** content margins 120 (1200 wide). Nav 88 tall (**NOT to be built, see decisions**). Hero (860 tall): pill label "FINANCIAL RESEARCH, WITH CLARITY"; h1 two lines "From financial reports" / "to confident answers." (second line accent colour, ≈60px); subtitle; buttons "Start analyzing →" (primary) and "Explore demo"; small line "No account needed to try · PDF reports · English & Vietnamese"; product preview card 1136×390 (mini sidebar, mini conversation, mini source panel) + caption "PRODUCT PREVIEW · EXAMPLE DATA". "How it works" (320): title "A simpler path from question to insight.", 3 columns 01/02/03 (Bring your reports / Ask what matters / See the evidence) separated by thin lines. "Research capabilities" (520, light grey band): eyebrow "MADE FOR FINANCIAL RESEARCH", title "More clarity. Less digging.", two cards 588×322: (a) "Compare performance, with context." with FY2023 growth bars 26.1% vs 5.7%; (b) "No source? No assumption." with a question "What was Amazon's revenue in FY2015?" and an amber warning "The selected filing covers FY2018, not FY2015." + link "Add another report →". Trust band (300, navy): eyebrow "BUILT AROUND THE SOURCE", title "An answer is only as useful as the evidence behind it.", three rows with check tiles (Selected reports only / Page-level references / Session-isolated documents). FAQ (360): left title "A few things you might be wondering.", right accordion (What can I upload? [open] / Can I compare more than one company? / How do I check the assistant's answers? / Is FinHelp a substitute for financial advice?). CTA band (240, `#edf1ff`): "Your reports hold the answers." + "Spend less time searching for them." + same two buttons + "Start with a PDF. No account needed to try." Footer (120): logo, "Clarity in every filing.", links How it works / Features / Trust / Sign in, "© 2026 FinHelp", "Research assistance, not investment advice."

## 2. Decisions already made by the owner

1. Keep **dark** exactly as the app looks today (default theme). Add **light** from the Figma. Dark and light CSS must stay in sync across the WHOLE project, not only the new pages.
2. **Landing page floating navbar (`fh-navbar-floating`) stays as it is** (only its colours were tokenised). Do not replace it with the flat Figma nav. (Open question: its links include "Use Cases"; see §5 Phase 5.)
3. **Admin pages keep their layout.** They only need light mode.
4. All other pages (landing, workspace, auth pages) are rebuilt from the Figma, except what the Figma does not show.
5. Figma has no frames for Login / Register / Forgot password / AuthModal: restyle them with the new tokens in the same visual language (demo tab 04 shows the intent). Ask the owner if they want real designs.
6. Default theme is dark; the saved choice lives in `localStorage` key `finhelp_theme`.

## 3. Done (Phases 1-2, commit `df6017b`)

- `src/index.css`: two colour-token blocks, `:root, [data-theme="dark"]` and `[data-theme="light"]`, same names in both (58 tokens in each block: surfaces, borders, text, accent, status, `--side-*` navy sidebar, `--band-*` landing bands, `--pdf-*`/`--paper-*`, highlight, scrim, shadow). Existing token names were kept so Tailwind (`@theme inline` names such as `bg-card`, `text-fg`, `border-line`, plus new `bg-elevated`, `text-accent-text`, `bg-accent-soft`, `text-danger`) and old CSS still work. `.theme-toggle` button style lives there too.
- `public/theme-init.js` sets `data-theme` on `<html>` before first paint. It is a separate file because the production build adds a CSP with `script-src 'self'` (see `vite.config.ts`): **an inline script would be blocked in production**.
- `src/context/ThemeContext.tsx` (`ThemeProvider`, `useTheme`), wrapped in `main.tsx`. `src/components/common/ThemeToggle.tsx` exists but is **not mounted anywhere yet**. Locale strings `common.switchToLight` / `switchToDark` added (en, vi, types).
- Every colour literal in CSS/TSX moved to a token by role. `scripts/check-theme-tokens.mjs` (`npm run test:theme`) fails on: a hex/rgb/hsl literal outside `index.css` (a line containing the marker `theme-ok` is allowed: logo brand colours in `FinHelpLogo.tsx`, the two chart series colours in `UsageCharts.tsx`), a `var(--x)` that is never defined, or a token present in only one theme block. `--color-*` names from `@theme inline` do not count as defined for `var()`.
- Dark fidelity: measured by re-running the mapping on the original CSS from git. 113 of 691 mapped spots shifted slightly (greys and blues a few shades; 16 old `#64748b` texts now use `--text-dim`, deliberately a bit lighter for contrast). Two real mistakes were found and fixed (toast backgrounds, navy overlays).
- Checked in the browser (both themes): `/` landing, `/app` empty workspace with the Sources drawer and PDF pane open, `/login`. **Not checked** (needs a backend): a real answer with table and citations, the PDF with highlights, register / reset pages, admin.

## 4. Gap list: Figma vs current code (the work for Phases 3-6)

Workspace (frames 02/03). Code locations: `src/features/workspace/Workspace.tsx`, `components/layout/{Navbar,SplitLayout}.tsx` + `layout.css`, `components/chat/{ChatContainer,ChatHistoryList,CitationBadge,AnswerActions,MarkdownRenderer}.tsx` + `chat.css`, `components/notebook/{SourceViewer,DocumentManager}.tsx` + `notebook.css`.

| # | Area | Figma | Code today |
|---|---|---|---|
| 1 | Logo / nav | logo, "New analysis", search with ⌘K, nav "Analyses" and "Document library", "Recent analyses" in the sidebar | logo is in the top Navbar; sidebar has only New analysis, history, search (only with ≥3 chats), no Document library page, no ⌘K |
| 2 | Header | breadcrumb "Workspace › title", Export button, EN/VI, (+ theme toggle) | Navbar: sidebar button, logo, "V3" badge, notebook title, "Filings: N" button, "Split view [On/Off]" button, language, user chip |
| 3 | Answer | answer in a bordered card: FinHelp avatar, green badge "N source references", big headline, summary, table | assistant text has no card (`.chat-message-bubble.assistant` is transparent) |
| 4 | Sources under answer | two cards: number, file name, "p.45 · Income statement", arrow | chips `[1] Page 45` (`CitationBadge`). `CitationItem` (`types/chat.ts`) has only `document_id`, `page`, `snippet`: file name can come from the document list, the **section name ("Income statement") does not exist in the data** → show file + page, or ask the owner to add a backend field |
| 5 | Table | uppercase header, green YoY, Source column with chips | already close (`financial-markdown-table`, `delta-positive`) |
| 6 | Actions | Copy answer, Report an issue, disclaimer, one follow-up suggestion chip | Copy + Report exist; suggestions are 3 static chips shown only when ≤3 messages. Contextual follow-ups need backend: skip, keep static |
| 7 | Composer | "+ N reports in scope" chip inside, round up-arrow send, hint row with "Check important figures against the source." | textarea + send, `@` mentions; scope only in the header |
| 8 | Scope bar | "N reports selected", company·period chips, "Manage ⌄" | label + up to 2 chips + "+N" + Manage button: add the "N reports selected" text |
| 9 | Source panel | "Source preview", dropdown "All reports (N)" instead of tabs, editable page box, fullscreen, "Highlighted in source" chip, explanation card, close X | one tab per file, "Page X of Y" text, no fullscreen; banner appears only when the highlight FAILS |
| 10 | Guest block | one "Your private workspace – Sign in to save →" card at the bottom of the sidebar | three places: Navbar badge, Navbar Sign-in button, banner above the list |
| 11 | Widths | sidebar 232, chat 760, source panel 448, no separate Sources drawer drawn | sidebar 270; with the PDF open chat is 45%; extra 320px Sources drawer |
| 12 | Demo-only text | "Sample data", "Illustrative answer · Sample documents", "Sample filing …" | do NOT ship these |
| S1 | Start screen | upload zone in the middle of the page, 3-step bar, 3 example-question cards, "Session-only · Not saved" | empty state is only a title, a sentence and a "choose filings" button; upload lives in the right-hand Sources drawer (`DocumentManager`) |

Landing (frame 01, `src/features/landing/LandingPage.tsx/.css`, 1113 + 2176 lines): code sections today = floating navbar, hero (+ big mockup), "The problem", Features, How it works, Use cases, Trust, final CTA, footer. Figma = hero (new headline, 2 buttons, preview card), How it works (3 steps), 2 capability cards, navy trust band, **FAQ (new)**, CTA band, footer. Figma drops "The problem" and "Use cases".

## 5. Remaining phases (do one at a time, report, wait for a go)

**Phase 3: workspace layout per Figma (frame 03).** Rebuild header, sidebar, answer card, source cards, composer, source panel. **Mount `ThemeToggle` in the new header.** Keep all existing behaviour: streaming/loading stages, `AnswerActions` (search deeper / change sources / edit / search all), `@` mentions, Flag/report, retry buttons, notebook rename/delete, Ctrl+B sidebar, mobile drawer rules (`@media` 1100 / 768 in `layout.css`), PDF page jump + highlight (`SourceViewer`, `locateExcerpt.ts`). Open/close of the Sources drawer and PDF pane must stay reachable once the "Filings" and "Split view" buttons are gone (use "Manage" in the scope bar and the X in the panel). Export button: **not decided**: do not build a fake one; leave it out or ask. "Document library" nav item: no such page exists: ask the owner (hide it, or route to the Sources drawer). Sidebar must use `--side-*` tokens (navy in both themes); panels use `--bg-sidebar` (white in light).

**Phase 4: Start analysis screen (frame 02).** Replace the empty state in `ChatContainer` (shown when the chat has no messages/sources) with the upload screen. Reuse the upload logic of `DocumentManager` (`docs.uploadFiles`, drag-drop, `isUploading`, `maxSources`, `maxFileSizeMb` from `useWorkspace`): the limits shown ("5 MB", "1 report in guest mode") must come from that config, not be hard-coded. Step bar follows state (no report → step 1; report ready → step 2; answer shown → step 3). Example cards insert their question into the composer (they cannot send without a report). Add all strings to the 3 locale files (EN + VI).

**Phase 5: Landing (frame 01) except the navbar.** Keep `fh-navbar-floating` untouched. Rebuild hero copy, preview card, How it works, capability cards, trust band, FAQ (use `<details>`/`<summary>`, no JS), CTA band, footer. Remove "The problem" and "Use cases" sections (owner saw them dropped in the demo). Open question: the floating navbar has a "Use Cases" link: remove that link if the section goes (tell the owner). EN + VI text for everything new.

**Phase 6: auth pages + admin + theme toggle everywhere.** (a) Restyle `features/auth/{LoginPage,RegisterPage,ResetPasswordPage}.tsx` + `auth-pages.css` and `components/auth/AuthModal.tsx` + `auth.css` to the demo tab 04 look (tokens only). (b) Admin keeps its layout but must follow the theme: 38 hard-coded Tailwind palette classes (`bg-slate-*`, `text-white`, …) in `features/admin/{AdminLayout(12),ui(8),DocumentsPage(4),AuditPage(3),OverviewPage(3),UsersPage(3),TokensPage(2),UsageCharts(2)}.tsx` and one in `Navbar.tsx` do not change with the theme: replace with token classes (`bg-card`, `bg-app`, `text-fg`, `text-muted`, `border-line`, …; see `@theme inline` in `index.css`). Extend `scripts/check-theme-tokens.mjs` to fail on those palette classes. (c) Put a `ThemeToggle` on the landing page area, auth pages and admin header too. (d) Final sweep with the contrast audit (below) in both themes on every route.

Optional later: add vitest + Testing Library so UI behaviour can be tested first (there is no runner today, so tests so far are `test:theme` and the browser checks).

## 6. How to verify (and traps)

Commands, from `frontend/`:

```
npm run test:theme        # must stay green
npx tsc --noEmit          # must stay clean
npx vite build            # must build
```

Run the app with the `frontend` preview config (`.claude/launch.json`, port 5173, may move to 5174). `/`, `/app` (guest) and `/login` render **without a backend**; a real answer, the PDF highlight and admin need the backend (`backend-dev` launch config, needs the GPU tunnel URL: ask the owner). Admin login: user `admin`, password = `ADMIN_PASSWORD` in `backend/.env` (never print it).

Traps found the hard way:
1. **The browser pane does not paint frames**, so colour transitions stay at their old values and `getComputedStyle` lies right after switching theme. Inject `*,*::before,*::after{transition:none!important;animation:none!important}` first, then set `document.documentElement.dataset.theme='light'`, then read. Screenshots are fine.
2. The pane is small: call `resize_window` (1440×900) before screenshots, and reset with the `desktop` preset when done. The pane tab can be closed by the user (sessionStorage is lost with it).
3. A Tailwind `@theme inline` name such as `--color-danger` is **not** a real CSS variable: `var(--color-danger)` is empty. Use the plain token (`var(--danger)`).
4. Inline `<script>` in `index.html` breaks the production CSP: put scripts in `public/`.
5. In CSS, `color:` inside `border-color`/`background-color` lines can fool a naive search: match from line start.
6. When you must compare with the original UI, stash only the frontend (`git stash push -- frontend`), never the whole tree (the four backend files are not yours).

Contrast audit: run this in the page console in both themes on each route. It lists text with contrast under 3:1 (white-on-white bugs show up here):

```js
const parse=c=>{const m=c.match(/rgba?\(([^)]+)\)|color\(srgb ([^)]+)\)/);if(!m)return null;if(m[1]){const p=m[1].split(/[ ,\/]+/).map(Number);return{r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}}const p=m[2].split(/[ \/]+/).map(Number);return{r:p[0]*255,g:p[1]*255,b:p[2]*255,a:p.length>3?p[3]:1}};
const lum=({r,g,b})=>{const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(r)+.7152*f(g)+.0722*f(b)};
const mix=(t,b)=>({r:t.r*t.a+b.r*(1-t.a),g:t.g*t.a+b.g*(1-t.a),b:t.b*t.a+b.b*(1-t.a),a:1});
const bgOf=el=>{const s=[];for(let e=el;e;e=e.parentElement){const c=parse(getComputedStyle(e).backgroundColor);if(c&&c.a>0){s.push(c);if(c.a>=1)break}}let base=parse(getComputedStyle(document.body).backgroundColor)||{r:255,g:255,b:255,a:1};if(s.length&&s[s.length-1].a>=1)base={r:0,g:0,b:0,a:1};for(let i=s.length-1;i>=0;i--)base=mix(s[i],base);return base};
[...document.querySelectorAll('body *')].filter(el=>[...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim().length>1)&&el.getBoundingClientRect().width>0).map(el=>{const fg=parse(getComputedStyle(el).color),bg=bgOf(el),f=mix(fg,bg),a=lum(f),b=lum(bg);return[(Math.max(a,b)+.05)/(Math.min(a,b)+.05),el.tagName+'.'+el.className,el.textContent.trim().slice(0,24)]}).filter(x=>x[0]<3).slice(0,40)
```

## 7. Open questions for the owner (ask when you reach them)

- Export button: build it (what does it export?) or leave it out.
- "Document library": hide it, or point it at the Sources drawer.
- Source cards need a section name ("Income statement"): add it to the backend citation, or show file + page only.
- Contextual follow-up suggestions after an answer (backend work): later, or never.
- Auth pages: confirm the invented style (demo tab 04) or send real designs.
- Landing navbar "Use Cases" link once that section is removed.

## 8. Status after Phases 3-6 (18/11/2026, uncommitted)

Owner decisions taken during the work: no Export button; "Document library" opens the Sources drawer; the landing navbar lost its "Use Cases" link; report after every phase.

- **Phase 3 (workspace):** navy full-height sidebar (`history.css`), top bar = breadcrumb + `ThemeToggle` + EN/VI (`Navbar.tsx`), answer card + `SourceCard.tsx` (replaces `CitationBadge`), composer with scope chip, 448px source preview (`SourceViewer.tsx`: report dropdown, page box, native full screen, highlight bar). Under 1480px only one side panel (Sources drawer or PDF) is open at a time. The guest's sign-in button shows in the top bar only while the sidebar is closed.
- **Phase 4 (start screen):** `StartScreen.tsx` + `start.css`, passed to `ChatContainer` as the render prop `startScreen`. Upload logic shared in `hooks/usePdfDrop.ts` (the Sources drawer uses it too). Limits shown come from the quota. Left out: Figma's "Try a demo" link (the app has no demo).
- **Phase 5 (landing):** `LandingPage.tsx` rebuilt except the floating navbar; `LandingPage.css` now holds only the navbar and the shell; sections are in `landing-sections.css` (`lp-*`). Whole `landing` locale block replaced. Figma's "Explore demo" became "See how it works" (anchor). FAQ uses `<details>`, guest limits come from `guestQuota`.
- **Phase 6:** sign-in pages and modal restyled (tab 04 look, card radius 18, soft glow, fields 9px radius); a real light-theme bug fixed (`.auth-submit-btn` had dark text on blue). Admin: all 38 Tailwind palette classes replaced by token classes (new names in `@theme inline`: `text-negative-text`, `text-warn-text`, `bg-hover`, `text-on-accent`, `bg-scrim`, ...). `npm run test:theme` now also fails on any palette class in a `.tsx`. `ThemeToggle` is mounted in the workspace top bar, the landing navbar, the three sign-in pages, the sign-in modal and the admin header.
- **Checked:** `tsc`, `test:theme`, `vite build` green; contrast audit (section 6) empty on `/`, `/login`, `/register`, `/reset-password`, `/app` in both themes, and on the five admin pages in light (admin was driven by a temporary page with made-up data, since removed). Layouts looked at 1440 / 1000 / 390 px, EN and VI.
- **Not checked (needs backend or a person):** a real answer with citations and the PDF highlight on a long report; uploading a real PDF; the browser pane refuses the Fullscreen API, so the source preview's full-screen button is untested; admin with real data; admin in dark after the token change was only looked at once.
- **Still open:** contextual follow-up suggestions after an answer (needs backend); real designs for the sign-in pages if the owner has them; unused locale keys may remain (the three `sidebar.isolatedFiling`-style leftovers); optional vitest + Testing Library.

### 8b. Fixes after trying the app signed in as admin (18/11/2026, uncommitted)
- Question box: font 14.5px (was 13), send button stays beside the last line while the box grows, height read from the CSS `max-height` (180px, 120px on a phone) and recomputed when the box's width changes (a panel opening); the message list stays at its end while the box grows (`pinnedRef` + `ResizeObserver` in `ChatContainer`). Note: the built-in browser pane only runs `ResizeObserver` callbacks when it paints (a screenshot forces it), so measure after a screenshot.
- Waiting state: the old `.chat-loading-*` classes had NO CSS at all (no spinner). Now one card: status line + spinner, three skeleton bars, a 4-step bar (understand, search, write, check). When the answer's card is already on screen (the "I understood the question as…" note arrives first) the block goes inside that card, not under it as a second card.
- Opening the source preview below 1320px closes the sidebar (chat stays about 620px or more); the user chip's name is cut with an ellipsis (150px).
- Backend, not done: correct answers get the line "This search may be incomplete because the system was slow…" when the search stage takes about 20 s.
- **Question box per chat (18/11):** `ChatContainer` takes `chatKey` (the notebook id) and keeps one unsent draft per chat in a `Map`; switching chats shows the draft of the chat you land in (empty if none), `@` tags are cleared. In memory only: a reload drops drafts.
