FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY app ./app
COPY public ./public
COPY tsconfig.json next-env.d.ts next.config.ts postcss.config.mjs ./
COPY docker/vite.config.ts ./vite.config.ts
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]


