# Stage 1: Build
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=""
ARG VITE_MOCK_MODE="false"
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_MOCK_MODE=$VITE_MOCK_MODE
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:1.27-alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
