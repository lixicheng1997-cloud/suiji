# MinIO 桶 CORS 配置（直传用）

## 作用
H5 浏览器把文件 `PUT` 到预签名的 MinIO 地址时，浏览器按同源策略拦截跨域请求，
需要桶侧放行对应来源、方法和响应头。**App 原生请求不经过浏览器 CORS，不受此规则约束**；
小程序走 multipart 回退，也不需要这条规则。

规则文件：`scripts/minio-cors.json`
- `AllowedOrigin`：H5 页面所在来源（当前生产入口 `http://49.233.77.155:30080`）；将来上 HTTPS 域名时把新来源也加进数组。
- `AllowedMethod`：`GET`（下载/校验）、`PUT`（直传）。
- `AllowedHeader`：直传请求携带的头。
- `ExposeHeader`：回传给浏览器可读的头（ETag）。

## 方式一：MinIO 控制台（图形）
1. 访问 MinIO 控制台（`9001` 端口，生产未对公网放行时走 SSH 隧道或临时绑定回环）。
2. 登录后进入 Buckets → `suiji` → Access Policy / CORS。
3. 新增一条规则，内容对齐 `minio-cors.json`：
   - Allowed Origin: `http://49.233.77.155:30080`
   - Allowed Methods: `GET`, `PUT`
   - Allowed Headers: `Content-Type`, `Content-Length`, `User-Agent`
   - Expose Headers: `ETag`

## 方式二：mc 命令行（一次性 mc 容器，复用 compose 网络）
在 `suiji-server` 目录下，把 `<MINIO_ROOT_USER>` / `<MINIO_ROOT_PASSWORD>` 替换为 `.env.prod` 里的值：

```bash
docker run --rm \
  --network suiji-server_default \
  -v "$PWD/scripts/minio-cors.json:/cors.json:ro" \
  minio/mc:latest sh -c \
  "mc alias set local http://minio:9000 <MINIO_ROOT_USER> <MINIO_ROOT_PASSWORD> && \
   mc cors set local/suiji /cors.json && \
   mc cors get local/suiji"
```

> 网络名以 `docker network ls` 里本项目 compose 实际创建的为准（通常是 `<目录名>_default`）。
> 规则只配一次，持久化在桶数据里；重建 MinIO 容器不丢。

## 直传生效的配套检查
- `.env.prod` 的 `MINIO_PUBLIC_URL` 指向 nginx 反代前缀：`http://49.233.77.155:30080/minio`（末尾不带斜杠）。
- nginx `/minio/` 反代已在 `nginx/templates/default.conf.template` 配好，透传 PUT 并保留原始 Host。
- 改完 `.env.prod` 后需重启 api：`docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d`。
- 直传任一步不可用，前端会自动回退现有 multipart `/files`，不会中断上传。
