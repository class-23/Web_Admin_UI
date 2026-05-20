"""
FastAPI 应用工厂
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.database import init_db
from app.routers import auth, pages

logger = logging.getLogger("QuantClaw")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("正在初始化数据库...")
    init_db()
    logger.info("数据库已就绪")
    yield
    logger.info("应用正在关闭...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="QuantClaw Admin UI",
        version="2.0.0",
        description="QuantClaw 设备管理后台",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory="static"), name="static")

    app.include_router(auth.router)
    app.include_router(pages.router)

    return app
