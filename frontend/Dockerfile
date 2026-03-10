### Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copia package files e instala dependencias
COPY package.json package-lock.json* ./
RUN npm ci

# Copia o codigo e faz o build
COPY . .
RUN npm run build

### Stage 2: Serve com Nginx
FROM nginx:alpine

# Remove config padrao do Nginx
RUN rm /etc/nginx/conf.d/default.conf

# Copia config customizada
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copia o build
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
