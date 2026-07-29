# Build stage
FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .

ARG VITE_API_BASE
ARG VITE_WS_BASE
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_WS_BASE=$VITE_WS_BASE

RUN npm run build

# Production stage
FROM nginx:alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
