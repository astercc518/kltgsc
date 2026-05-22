import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import mdx from '@mdx-js/rollup';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import path from 'node:path';

export default defineConfig({
  plugins: [
    // MDX must come before @vitejs/plugin-react so JSX produced by mdx
    // gets transformed by the react plugin too.
    {
      enforce: 'pre',
      ...mdx({
        providerImportSource: '@mdx-js/react',
        remarkPlugins: [remarkGfm],
        rehypePlugins: [rehypeHighlight],
      }),
    },
    react({ include: /\.(mdx|md|jsx|tsx)$/ }),
  ],
  base: '/',
  build: {
    assetsDir: 'landing-assets',
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
