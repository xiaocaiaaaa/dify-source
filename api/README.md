# 0.15.3版本 本地源码部署
1. 启动api：
```shell
cd api
pyenv global 3.12
poetry env use 3.12
poetry install
```
+ 可以直接命令行启动：
  + poetry run flask db upgrade
  + poetry run flask run --host 0.0.0.0 --port=5001 --debug

+ 如果需要调试异步操作，可以启动worker服务 
  poetry run celery -A app.celery worker -P gevent -c 1 --loglevel INFO -Q dataset,generation,mail,ops_trace
2. 启动web：
```shell
cd web
pnpm install --frozen-lockfile
npm run dev
```

# 1.x版本 本地源码部署
1. 启动api：
```shell
cd api
pyenv global 3.12
poetry env use 3.12
poetry install
```
+ 可以直接命令行启动：
  + uv run flask db upgrade
  + uv run flask run --host 0.0.0.0 --port=5001 --debug

+ 如果需要调试异步操作，可以启动worker服务 :
  + uv run celery -A app.celery worker -P gevent -c 1 --loglevel INFO -Q dataset,generation,mail,ops_trace
2. 启动web：
```shell
cd web
pnpm install --frozen-lockfile
npm run dev
```
