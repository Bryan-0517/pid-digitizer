FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
RUN npm ci
COPY apps/web ./apps/web
COPY benchmarks/hydrolysis/expected ./benchmarks/hydrolysis/expected
COPY benchmarks/hydrolysis/images/IMG_6807.JPG ./benchmarks/hydrolysis/images/IMG_6807.JPG
COPY benchmarks/hydrolysis/evaluations/fixtures/IMG_6807.openai-gpt5.tiled-20260816-02-validation-v1.proposal.json ./benchmarks/hydrolysis/evaluations/fixtures/IMG_6807.openai-gpt5.tiled-20260816-02-validation-v1.proposal.json
WORKDIR /app/apps/web
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
