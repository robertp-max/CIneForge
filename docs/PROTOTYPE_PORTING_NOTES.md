# Prototype Porting Notes

Reviewed visual/interaction references: `components/AppShell.tsx`, `pagesCore.tsx`, `pagesAssets.tsx`, `pagesOps.tsx`, `pages.ts`, `ui.tsx`, `data/mockProject.ts`, `state/projectStore.tsx`, `types/cineforge.ts`, `app/globals.css`, and `app/page.tsx` from Storyboard Studio v2.

Ported: dark charcoal/mint Studio language, compact navigation, ten planning views, hierarchy workspace, selected-shot inspector, approval/readiness presentation, exports, and Preview Animatic disclaimer. The real app uses FastAPI, SQLAlchemy, Alembic, PostgreSQL-compatible storage, and Vite; prototype Next/Vinext, Drizzle, worker, build, script, and Cloudflare infrastructure was intentionally excluded.
