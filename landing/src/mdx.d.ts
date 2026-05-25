/// <reference types="vite/client" />

/**
 * Type stubs for *.mdx imports.
 *
 * @mdx-js/rollup emits a React component as the default export of every
 * mdx file. Without this declaration, TypeScript errors on
 * `import Article from './foo.mdx'`.
 */
declare module '*.mdx' {
  import type { ComponentType, ComponentPropsWithoutRef } from 'react';
  const MDXComponent: ComponentType<ComponentPropsWithoutRef<'div'>>;
  export default MDXComponent;
}
