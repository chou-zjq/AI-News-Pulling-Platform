"""
AI 新闻调取平台 — FastAPI 入口。
"""

import sys
from contextlib import asynccontextmanager

# 修复 Windows GBK 下 emoji 打印报错
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from models.database import Database
from routers import api, keybox_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库，关闭时清理连接"""
    Database.get().init_db()
    print("✅ 数据库初始化完成")
    yield
    Database.get().close()
    print("✅ 数据库连接已关闭")


app = FastAPI(
    title="AI 新闻调取平台",
    description="自动抓取、整理 AI 相关新闻，生成每日记录本",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api.router)
app.include_router(keybox_api.router)


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "version": "0.1.0"}


# ═══ 启动入口 ═══
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
