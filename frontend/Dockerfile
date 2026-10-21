# ==============================================================================
# Stage 1: Build the React Application using Node.js
# ==============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests first to leverage Docker layer caching
COPY package.json ./

# Install project dependencies
RUN npm install

# Copy application source code
COPY . .

# Build the production bundle with Vite
RUN npm run build

# ==============================================================================
# Stage 2: Serve static assets with lightweight Nginx web server
# ==============================================================================
FROM nginx:1.27-alpine

# Set working directory
WORKDIR /usr/share/nginx/html

# Remove default Nginx welcome assets
RUN rm -rf ./*

# Copy built static assets from Stage 1
COPY --from=builder /app/dist .

# Copy custom Nginx configuration with reverse proxy rules
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Configure directory permissions for enhanced security
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid /var/cache/nginx

# Expose HTTP port 80
EXPOSE 80

# Health check using Alpine's built-in wget
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/frontend-health || exit 1

# Launch Nginx in foreground mode
CMD ["nginx", "-g", "daemon off;"]
