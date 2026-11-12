# forbidden-word — config panel

SvelteKit single-page app (static build, `adapter-static`), Tailwind CSS 4, Svelte 5 runes.

```powershell
npm run dev      # http://localhost:5173, talks to the backend on :8765
npm run build    # static build in build/, served by the backend on http://localhost:8765/
npm run check    # svelte-check
npm run lint     # prettier + eslint
```

- `src/lib/app.svelte.ts`: app state, WebSocket events, auto-save of the config
- `src/lib/i18n.svelte.ts`: English / French texts
- `src/lib/components/`: tabs and live panel; `src/lib/ui/`: switch, slider, option buttons
- `src/routes/layout.css`: Cybercore theme (tokens and shared utilities)
- `src/lib/dev/`: development-only helpers (not in the build)
