# Repository Guidelines

## Project Structure & Module Organization

AMQUANT is organized as a small workspace: `frontend/` contains the React interface, `backend/` contains the FastAPI service, and `quant_engine/` contains pure, reusable financial calculations. Keep calculation code independent of HTTP and UI code. Tests live beside each project under `tests/`; shared architecture notes are in `docs/`.

## Build, Test, and Development Commands

From the root, run `npm install` then `npm run dev` for the frontend, `npm run build` for a production build, and `npm test` for frontend tests. For Python, create a virtual environment, install `backend/requirements.txt`, then run `python -m uvicorn backend.app.main:app --reload` and `python -m pytest`. Use Python 3.10+ and Node 20+.

## Coding Style & Naming Conventions

TypeScript uses two spaces, single quotes, and semicolons; React components use PascalCase filenames and names. Python uses four spaces, snake_case, and type hints for public functions. Keep frontend components presentational and put quantitative logic in `quant_engine/`. Follow existing formatting and avoid unrelated reformatting.

## Testing Guidelines

Frontend tests use Vitest and Testing Library (`npm test`). Python tests use pytest (`python -m pytest`). Name tests `*.test.tsx`/`*.test.ts` or `test_*.py`. Add numerical tests for edge cases and financial invariants whenever changing the quant engine; do not rely on visual checks for mathematical correctness.

## Commit & Pull Request Guidelines

No Git history is available to establish a commit message convention. Write concise commit subjects in the imperative (for example, `Add portfolio validation`). Pull requests should explain the change and its motivation, list relevant checks and their results, and link related issues when applicable. Include screenshots for changes that affect a user interface.

## Security & Configuration Tips

Do not commit credentials, API keys, or machine-specific configuration. Provide safe examples or a documented template for required settings, and keep real secrets in the local environment or an approved secret store.
