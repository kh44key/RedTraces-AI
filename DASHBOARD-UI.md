# RedTraces intelligence workspace

The editorial cyber console runs at http://localhost:3000 with the existing Compose stack. Inspired by the spacing and hierarchy of https://cyberfz.webflow.io/home, the theme uses near-black (#0B0C0E), charcoal (#141518), ivory (#F5F4EF), and crimson/red accents. Primary actions use a crimson gradient with white labels; the RedTraces wordmark uses two red tones. Supporting chart colors distinguish labelled series. Locally hosted Manrope and Space Grotesk keep typography consistent without runtime third-party font requests. Existing console styles supply layout; agency.css is the final theme layer.

## Modes

- **Demo (default)**: 96 fictional signals across six platforms, 32 documentation-only observables, sample filtering counters, watchlists, qualification decisions, forward-trace examples and reviewable evidence. Demo watchlists, qualification decisions and review status persist in this browser only. All dates are relative to the sample generation time. Refresh regenerates the sample feed; it does not run crawlers.
- **Live**: reads only the connected APIs. There is no synthetic-data fallback. Empty or unavailable modules are explicitly identified. The overview represents loaded records within the selected date range, not a full database total. The feed currently reads up to 200 core messages, 150 forum records, and 1,000 records per social collector.

## Preserved functionality

The original Telegram, dark-forum, X, Facebook and Instagram collectors and connection settings remain available in Live mode. Their keyword search, targets, account visibility, forum date/severity filters and add-target controls are retained in `app/legacy-collectors.tsx`. Existing API endpoints, database volumes and credentials were not changed.

The intelligence navigation includes live signals, IOC explorer, STIX store, confidence, risk scoring, source correlation, noise filtering, rule authoring, deployment audit, artifact review and reporting. Watchlists, qualification, forward tracing and ATT&CK coverage have interactive demo views. This UI does not implement missing live collection/AI endpoints or falsely report them as active.

## Exports and safeguards

- JSON report exports include data mode, time scope and loaded evidence.
- STIX 2.1 export represents supported IPv4, domain and URL values as cyber-observable objects, not confirmed malicious indicators. Other types are explicitly omitted in this UI export.
- Sigma and YARA workbenches download local experimental drafts. No SIEM deployment is triggered.
- The demo does not join Telegram channels, crawl websites, spend API credits or train a model.
- The forward-trace example illustrates visible edges only. It does not claim complete forwarding history or identity attribution.

## Interaction and accessibility

Responsive sidebar, keyboard navigation, labelled forms, modal focus trap, Escape-to-close, Ctrl/Cmd+K search, chart focus details, hover states, evidence inspection and reduced-motion support. The header animation toggle disables motion; operating-system reduced-motion preferences also take precedence.

Motion is coordinated in agency-motion.tsx using native Web Animations, IntersectionObserver, and passive scroll listeners throttled by requestAnimationFrame. Hero lines stagger by 100ms, then the supporting copy and CTA enter. The hero image reveals through a mask. Panels enter once per mount with 600ms upward fades; statistic counts run once. View changes use 350ms fades. Fine-pointer devices get a primary CTA magnetic offset capped at 8px, 4px card lift, and hero parallax capped at 20px. The navbar becomes translucent on scroll and a 2px reading-progress line tracks page position. Continuous decorative loops and the old rotating globe have been removed from the rendered overview.

One three-stage workflow story follows the analytical overview. It becomes sticky on desktop, with 450ms transitions and keyboard-accessible step controls. It becomes ordinary stacked content on mobile and in reduced-motion mode. The operating-system preference and existing header motion toggle disable the choreography. No scroll-jacking, animation library, or third-party animation service is used. These interactions never change evidence or totals.

The activity chart plots collected signals and high-priority signals from actual selected demo/live records. Charts remain lightweight SVG/CSS with data-derived totals. premium.css is retained but not imported.

## Artwork and font provenance

- Hero: user-supplied Gabriele Malaspina / Unsplash robot photograph, resized to public/images/cyber-portrait.jpg (1500px, approximately 186KB). Original file is unchanged.
- Supporting conceptual artwork: public/images/intelligence-core.jpg (1000px, approximately 137KB), generated with the built-in image_gen tool and optimized for web delivery. It is decorative, not observed telemetry or evidence.
- Generation prompt: “Use case: stylized-concept. Asset type: supporting artwork for a premium cybersecurity intelligence dashboard. Create a cinematic 3D product render of a precision-engineered cybersecurity data core: three concentric black titanium rings enclosing a smoked-glass faceted sphere, restrained warm amber luminous circuitry, tiny elegant connections, matte black studio background. Contemporary luxury technology editorial, physically realistic metals and glass, sharp highlights, tasteful restrained contrast. Centered composition, square aspect, generous black negative space, no text, no logos, no lettering, no watermark. This is decorative conceptual artwork, not a screenshot or real data visualization.”
- Fonts: Manrope and Space Grotesk, sourced from Google Fonts; SIL Open Font License copies accompany the self-hosted font files.

## Build and verification

```powershell
docker compose build dashboard
docker compose up -d --no-deps dashboard
node --test tests/intelligence-data.test.mjs
docker exec redtraces-ai-dashboard-1 npx tsc --noEmit --jsx react-jsx --target ES2022 --module ESNext --moduleResolution bundler --esModuleInterop --skipLibCheck --strict app/intelligence-console.tsx app/intelligence-data.ts app/telemetry-motion.tsx
```

Data tests require a Node version supporting native TypeScript stripping (Node 24 used locally). The inherited `npm test` suite references a removed starter skeleton; the command above specifically tests the new dashboard data contract.

### Verified for the red editorial update

Production Docker build and targeted strict TypeScript check passed. All five dashboard data tests passed. Browser checks covered desktop (1280px), tablet (820px), phone (390px), navigation to the IOC inventory and its evidence dialog, the three-state desktop story, and the in-app reduced-motion toggle. Tablet and phone have no horizontal page overflow; the phone hero image starts below the text. No browser errors were recorded in the checked overview. OS reduced-motion is implemented with matchMedia and CSS; OS preference emulation and Core Web Vitals benchmarking were not performed.
