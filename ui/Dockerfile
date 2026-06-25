FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
# package-lock.json is optional; npm install works without it
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# SPA static assets
COPY --from=build /app/dist /usr/share/nginx/html
# SPA-aware nginx config (history fallback + API proxy)
COPY nginx-ui.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
