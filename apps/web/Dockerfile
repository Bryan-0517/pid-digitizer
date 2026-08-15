FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN npm ci
COPY apps/web ./apps/web
WORKDIR /app/apps/web
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
