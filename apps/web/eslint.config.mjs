import { FlatCompat } from '@eslint/eslintrc';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const baseDirectory = dirname(fileURLToPath(import.meta.url));
const compat = new FlatCompat({ baseDirectory });
const config = [
  { ignores: ['**/.next/**', '**/node_modules/**', '**/test-results/**'] },
  ...compat.extends('next/core-web-vitals'),
  {
    rules: {
      // Evidence previews are dynamic same-origin SVG endpoints; Next Image cannot optimize them.
      '@next/next/no-img-element': 'off',
    },
  },
];

export default config;
