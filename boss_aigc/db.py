"""boss_aigc.db 数据库初始化与连接管理。

使用 SQLite 轻量数据库，开箱即用，无需额外安装。
所有平台业务数据（商品/订单/素材/营销/客服/财务）持久化到这里。
"""

from __future__ import annotations

import sqlite3
import json
import os
from datetime import datetime
from typing import Any, Optional
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "boss_aigc.db")

# DDL：建表语句
_SCHEMA = """
-- 商品表
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT DEFAULT '',
    price REAL NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0,
    stock INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'on_sale',  -- on_sale / out_of_stock / off_shelf
    image_url TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 每日销售统计
CREATE TABLE IF NOT EXISTS daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_date TEXT NOT NULL UNIQUE,
    gmv REAL NOT NULL DEFAULT 0,
    orders INTEGER NOT NULL DEFAULT 0,
    visitors INTEGER NOT NULL DEFAULT 0,
    conversion_rate REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- AI 任务记录
CREATE TABLE IF NOT EXISTS ai_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,           -- image_gen / copywriting
    product TEXT DEFAULT '',
    params TEXT DEFAULT '{}',          -- JSON
    status TEXT NOT NULL DEFAULT 'pending',  -- pending / executing / done / failed
    artifacts TEXT DEFAULT '[]',       -- JSON array
    cost INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

-- 素材库
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_type TEXT NOT NULL,          -- main / detail / scene / poster / carousel
    product_name TEXT NOT NULL,
    url TEXT DEFAULT '',
    thumbnail_url TEXT DEFAULT '',
    task_id INTEGER,
    created_at TEXT NOT NULL
);

-- 营销活动
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,                -- flash_sale / full_reduction / new_user / group_buy
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',  -- active / upcoming / ended
    discount_value REAL DEFAULT 0,
    conditions TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- 优惠券
CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,                -- full_reduction / discount / new_user
    value REAL NOT NULL,
    condition_amount REAL DEFAULT 0,
    claimed_count INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 100,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

-- 客服消息
CREATE TABLE IF NOT EXISTS customer_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    message_preview TEXT DEFAULT '',
    unread_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending / resolved
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 常见问题
CREATE TABLE IF NOT EXISTS faq (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- 财务记录
CREATE TABLE IF NOT EXISTS finance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type TEXT NOT NULL,         -- income / expense
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    description TEXT DEFAULT '',
    record_date TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 任务历史（资产层持久化）
CREATE TABLE IF NOT EXISTS task_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL UNIQUE,
    task_type TEXT NOT NULL,
    product TEXT DEFAULT '',
    raw_text TEXT DEFAULT '',
    summary_id TEXT DEFAULT '',
    params TEXT DEFAULT '{}',          -- JSON
    platform TEXT DEFAULT '',
    result_artifacts_count INTEGER NOT NULL DEFAULT 0,
    result_status TEXT DEFAULT '',
    timestamp TEXT NOT NULL
);

-- 品牌风格（资产层持久化，单条全局风格）
CREATE TABLE IF NOT EXISTS brand_styles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    style_id TEXT NOT NULL UNIQUE,
    keywords TEXT DEFAULT '[]',        -- JSON array
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
"""


def init_db() -> None:
    """初始化数据库：创建目录、建表、插入种子数据。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
    _seed_if_empty()


@contextmanager
def get_conn():
    """获取数据库连接上下文管理器。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 结果按字典访问
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().isoformat()


def _seed_if_empty() -> None:
    """首次启动时插入演示数据。"""
    with get_conn() as conn:
        # 检查是否已有数据
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count > 0:
            return

        now = _now()

        # 商品
        products = [
            ("北欧简约沙发", "家具", 2899, 1800, 45, "on_sale"),
            ("复古黄铜吊灯", "灯具", 599, 320, 28, "on_sale"),
            ("日式棉麻抱枕", "软装", 89, 35, 156, "on_sale"),
            ("实木茶几", "家具", 1299, 780, 12, "on_sale"),
            ("ins风装饰画", "装饰", 159, 60, 0, "out_of_stock"),
            ("手工编织地毯", "软装", 899, 450, 8, "on_sale"),
            ("香薰蜡烛套装", "生活", 199, 80, 67, "on_sale"),
            ("陶瓷餐具六件套", "餐厨", 329, 140, 23, "on_sale"),
        ]
        for name, cat, price, cost, stock, status in products:
            conn.execute(
                "INSERT INTO products (name, category, price, cost, stock, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (name, cat, price, cost, stock, status, now, now),
            )

        # 每日统计（最近7天）
        import random
        base_gmv = 8000
        for i in range(7, 0, -1):
            d = datetime.now().replace(hour=0, minute=0, second=0)
            from datetime import timedelta
            d = d - timedelta(days=i)
            gmv = base_gmv + random.randint(-2000, 4000)
            orders = int(gmv / random.uniform(120, 180))
            visitors = int(orders / random.uniform(0.025, 0.04))
            cr = round(orders / visitors * 100, 1) if visitors > 0 else 0
            conn.execute(
                "INSERT OR IGNORE INTO daily_stats (stat_date, gmv, orders, visitors, conversion_rate, created_at) VALUES (?,?,?,?,?,?)",
                (d.strftime("%Y-%m-%d"), gmv, orders, visitors, cr, now),
            )

        # AI 任务
        tasks = [
            ("image_gen", "北欧简约沙发", '{"image_type":"main","quantity":4}', "done", 8),
            ("copywriting", "日式棉麻抱枕", '{"type":"title"}', "done", 2),
            ("image_gen", "复古黄铜吊灯", '{"image_type":"scene","quantity":2}', "done", 4),
            ("image_gen", "陶瓷餐具六件套", '{"image_type":"detail","quantity":6}', "done", 12),
            ("copywriting", "香薰蜡烛套装", '{"type":"xiaohongshu"}', "done", 2),
        ]
        for ttype, product, params, status, cost in tasks:
            conn.execute(
                "INSERT INTO ai_tasks (task_type, product, params, status, cost, created_at, completed_at) VALUES (?,?,?,?,?,?,?)",
                (ttype, product, params, status, cost, now, now),
            )

        # 素材库
        assets = [
            ("main", "北欧简约沙发"), ("main", "北欧简约沙发"),
            ("scene", "复古黄铜吊灯"), ("scene", "复古黄铜吊灯"),
            ("detail", "陶瓷餐具六件套"), ("detail", "陶瓷餐具六件套"),
            ("poster", "香薰蜡烛套装"), ("carousel", "日式棉麻抱枕"),
            ("main", "手工编织地毯"),
        ]
        for atype, product in assets:
            conn.execute(
                "INSERT INTO assets (asset_type, product_name, url, thumbnail_url, created_at) VALUES (?,?,?,?,?)",
                (atype, product, "", "", now),
            )

        # 营销活动
        campaigns = [
            ("夏日清仓特卖", "flash_sale", "2026-07-01", "2026-07-31", "active", 50, "全场满200减50"),
            ("新品上市优惠", "full_reduction", "2026-07-15", "2026-08-15", "active", 30, "满500减30"),
            ("开学季大促", "group_buy", "2026-08-01", "2026-08-20", "upcoming", 20, "3人成团享8折"),
            ("新人专享礼", "new_user", "2026-06-01", "2026-12-31", "active", 15, "首单立减15元"),
        ]
        for name, ctype, start, end, status, discount, cond in campaigns:
            conn.execute(
                "INSERT INTO campaigns (name, type, start_date, end_date, status, discount_value, conditions, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (name, ctype, start, end, status, discount, cond, now),
            )

        # 优惠券
        coupons = [
            ("满200减50", "full_reduction", 50, 200, 78, 100, "active"),
            ("9折优惠券", "discount", 10, 0, 45, 200, "active"),
            ("新人15元券", "new_user", 15, 0, 156, 500, "active"),
        ]
        for name, ctype, value, cond, claimed, total, status in coupons:
            conn.execute(
                "INSERT INTO coupons (name, type, value, condition_amount, claimed_count, total_count, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (name, ctype, value, cond, claimed, total, status, now),
            )

        # 客服消息
        messages = [
            ("张小姐", "沙发有现货吗？什么时候能发货？", 2, "pending"),
            ("李先生", "吊灯安装麻烦吗？包安装吗？", 1, "pending"),
            ("王女士", "抱枕可以机洗吗？", 3, "pending"),
            ("赵先生", "地毯尺寸有1.5m的吗？", 1, "pending"),
            ("陈小姐", "餐具套装包含哪些？", 0, "resolved"),
        ]
        for cname, preview, unread, status in messages:
            conn.execute(
                "INSERT INTO customer_messages (customer_name, message_preview, unread_count, status, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (cname, preview, unread, status, now, now),
            )

        # FAQ
        faqs = [
            ("发货时间是多久？", "现货商品24小时内发货，定制商品3-5个工作日发货。", "物流", 0),
            ("支持哪些支付方式？", "支持微信、支付宝、银行卡转账，企业用户支持对公转账。", "支付", 1),
            ("退换货政策是什么？", "7天无理由退换货，商品质量问题运费由我们承担。", "售后", 2),
            ("可以开发票吗？", "可以开具电子发票和纸质发票，下单时备注即可。", "发票", 3),
            ("有实体店吗？", "我们在杭州有一家体验店，欢迎来店体验。", "其他", 4),
        ]
        for q, a, cat, sort in faqs:
            conn.execute(
                "INSERT INTO faq (question, answer, category, sort_order, created_at) VALUES (?,?,?,?,?)",
                (q, a, cat, sort, now),
            )

        # 财务记录
        finance = [
            ("income", "商品销售收入", 45800, "7月商品销售", "2026-07-01"),
            ("expense", "平台佣金", 6870, "各平台佣金扣点", "2026-07-01"),
            ("expense", "广告投放", 5200, "直通车+信息流广告", "2026-07-01"),
            ("expense", "物流仓储", 3500, "快递+仓库租赁", "2026-07-01"),
            ("expense", "素材制作", 2630, "AI出图+摄影外包", "2026-07-01"),
            ("income", "商品销售收入", 38200, "6月商品销售", "2026-06-01"),
            ("expense", "平台佣金", 5730, "6月各平台佣金", "2026-06-01"),
            ("expense", "广告投放", 4100, "6月广告投放", "2026-06-01"),
            ("income", "商品销售收入", 41500, "5月商品销售", "2026-05-01"),
            ("expense", "平台佣金", 6225, "5月平台佣金", "2026-05-01"),
            ("income", "商品销售收入", 35800, "4月商品销售", "2026-04-01"),
            ("expense", "平台佣金", 5370, "4月平台佣金", "2026-04-01"),
        ]
        for rtype, cat, amount, desc, date in finance:
            conn.execute(
                "INSERT INTO finance_records (record_type, category, amount, description, record_date, created_at) VALUES (?,?,?,?,?,?)",
                (rtype, cat, amount, desc, date, now),
            )
