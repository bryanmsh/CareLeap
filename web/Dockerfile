# CareLeap web — static build served by nginx (Railway service with root directory `web`).
#
# VITE_API_BASE is baked in at build time: set it as a Railway variable on this service
# to the API service's public URL, e.g. https://careleap-api.up.railway.app
FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE
ENV VITE_API_BASE=${VITE_API_BASE}
RUN test -n "$VITE_API_BASE" || (echo "Set VITE_API_BASE to the API's public URL" && exit 1)
RUN npx vite build

FROM nginx:1.27-alpine
# nginx's image renders /etc/nginx/templates/*.template with env vars at start, so the
# server listens on Railway's $PORT.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /web/dist /usr/share/nginx/html
ENV PORT=8080
EXPOSE 8080
