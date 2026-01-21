FROM node:18-alpine

WORKDIR /app

COPY package.json package-lock.json* ./

# 安装所有依赖
RUN npm install && npm install recharts

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
