FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN npm ci
COPY apps/web ./apps/web
COPY benchmarks/hydrolysis/expected ./benchmarks/hydrolysis/expected
COPY benchmarks/hydrolysis/images/IMG_6807.JPG ./benchmarks/hydrolysis/images/IMG_6807.JPG
WORKDIR /app/apps/web
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
