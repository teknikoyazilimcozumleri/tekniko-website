import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  site: "teknikoyazilimcozumleri.github.io",
  base: "/tekniko-website",
  vite: {
    plugins: [tailwindcss()]
  }
});