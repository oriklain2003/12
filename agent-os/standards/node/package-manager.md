# Node.js Package Manager: pnpm

Always use **pnpm** for Node.js/JavaScript/TypeScript package management.

## Rules

- Use `pnpm` instead of `npm`, `yarn`, or `bun`
- Use `pnpm install` to install dependencies (not `npm install`)
- Use `pnpm add <package>` to add dependencies
- Use `pnpm add -D <package>` to add dev dependencies
- Use `pnpm remove <package>` to remove dependencies
- Use `pnpm run <script>` or `pnpm <script>` to run scripts
- Use `pnpm dlx` instead of `npx` for one-off package execution
- Use `pnpm create` instead of `npm create` or `npx create-*`

## Project Setup

- Lock file: `pnpm-lock.yaml` (committed to version control)
- Node modules: `node_modules/` (not committed, uses pnpm's content-addressable store)
- For monorepos, use `pnpm-workspace.yaml`

## Common Commands

```bash
pnpm init                        # Initialize new project
pnpm install                     # Install all dependencies
pnpm add react next              # Add dependencies
pnpm add -D typescript eslint    # Add dev dependencies
pnpm run build                   # Run build script
pnpm dlx create-next-app@latest  # Scaffold with one-off package
pnpm test                        # Run tests
```
