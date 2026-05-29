# AI Code Reviewer 部署指南

## 方案一：云服务器部署（推荐）

### 1. 购买云服务器

推荐配置：
- **阿里云/腾讯云/华为云**
- 2 核 4G 内存
- Ubuntu 22.04 系统
- 带宽 5Mbps+

### 2. 安装 Docker

```bash
# SSH 登录服务器后执行
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 重新登录
```

### 3. 上传项目

```bash
# 方式一：使用 git
git clone <你的仓库地址>
cd ai-code-review

# 方式二：使用 scp 上传
scp -r ./ai-code-review root@服务器IP:/opt/
```

### 4. 配置环境变量

```bash
cd /opt/ai-code-review
cp .env.example .env
vim .env
```

填入你的配置：
```env
MIMO_API_KEY=你的MiMo API Key
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5-pro
SECRET_KEY=随机生成的密钥
```

### 5. 启动服务

```bash
docker-compose up -d
```

### 6. 访问

- 通过服务器 IP 访问：`http://你的服务器IP`
- 绑定域名后：`http://你的域名.com`

---

## 方案二：宝塔面板部署

### 1. 安装宝塔

```bash
wget -O install.sh https://download.bt.cn/install/install_ubuntu_6.0.sh && sudo bash install.sh
```

### 2. 安装 Docker 插件

在宝塔面板 → 软件商店 → 搜索 Docker → 安装

### 3. 上传项目

通过宝塔文件管理器上传项目文件

### 4. 部署

在宝塔终端执行：
```bash
cd /www/wwwroot/ai-code-review
docker-compose up -d
```

---

## 方案三：Serverless 部署（低成本）

### 后端部署到函数计算

1. 阿里云函数计算 / 腾讯云函数
2. 打包后端代码上传
3. 配置 API 网关触发器

### 前端部署到 OSS

1. 阿里云 OSS / 腾讯云 COS
2. 开启静态网站托管
3. 上传构建产物

---

## 域名配置

### 1. 购买域名

在阿里云/腾讯云购买域名

### 2. 域名备案

国内服务器需要备案（约 7-15 个工作日）

### 3. 配置域名解析

添加 A 记录，指向服务器 IP

### 4. 配置 HTTPS（推荐）

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 申请证书
sudo certbot --nginx -d your-domain.com
```

---

## 常见问题

### Q: 如何更新代码？

```bash
cd /opt/ai-code-review
git pull
docker-compose down
docker-compose up -d --build
```

### Q: 如何查看日志？

```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Q: 如何备份数据？

```bash
# 备份数据库
docker cp ai-review-backend:/app/data/ai_code_reviewer.db ./backup/

# 恢复数据库
docker cp ./backup/ai_code_reviewer.db ai-review-backend:/app/data/
```

### Q: 端口被占用怎么办？

修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "8080:80"  # 改为 8080
```

---

## 成本估算

| 方案 | 月费用 | 适合场景 |
|------|--------|----------|
| 云服务器 | ¥50-200 | 正式交付 |
| Serverless | ¥5-20 | 低流量测试 |
| 宝塔面板 | ¥50-150 | 运维友好 |

---

## 技术支持

如有部署问题，请联系开发者。
