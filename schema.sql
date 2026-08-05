-- BossAIGC Supabase 建表 SQL
-- 在 Supabase 控制台 > SQL Editor 中执行此文件

-- ========== 建表 ==========

-- 商品表
CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT DEFAULT '',
    price DOUBLE PRECISION NOT NULL DEFAULT 0,
    cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    stock INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'on_sale',
    image_url TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 每日销售统计
CREATE TABLE IF NOT EXISTS daily_stats (
    id BIGSERIAL PRIMARY KEY,
    stat_date TEXT NOT NULL UNIQUE,
    gmv DOUBLE PRECISION NOT NULL DEFAULT 0,
    orders INTEGER NOT NULL DEFAULT 0,
    visitors INTEGER NOT NULL DEFAULT 0,
    conversion_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- AI 任务记录
CREATE TABLE IF NOT EXISTS ai_tasks (
    id BIGSERIAL PRIMARY KEY,
    task_type TEXT NOT NULL,
    product TEXT DEFAULT '',
    params JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    artifacts JSONB DEFAULT '[]',
    cost INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- 素材库
CREATE TABLE IF NOT EXISTS assets (
    id BIGSERIAL PRIMARY KEY,
    asset_type TEXT NOT NULL,
    product_name TEXT NOT NULL,
    url TEXT DEFAULT '',
    thumbnail_url TEXT DEFAULT '',
    task_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 营销活动
CREATE TABLE IF NOT EXISTS campaigns (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    discount_value DOUBLE PRECISION DEFAULT 0,
    conditions TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 优惠券
CREATE TABLE IF NOT EXISTS coupons (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    condition_amount DOUBLE PRECISION DEFAULT 0,
    claimed_count INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 100,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 客服消息
CREATE TABLE IF NOT EXISTS customer_messages (
    id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    message_preview TEXT DEFAULT '',
    unread_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 常见问题
CREATE TABLE IF NOT EXISTS faq (
    id BIGSERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 财务记录
CREATE TABLE IF NOT EXISTS finance_records (
    id BIGSERIAL PRIMARY KEY,
    record_type TEXT NOT NULL,
    category TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    description TEXT DEFAULT '',
    record_date TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 任务历史（资产层持久化）
CREATE TABLE IF NOT EXISTS task_history (
    id BIGSERIAL PRIMARY KEY,
    task_id TEXT NOT NULL UNIQUE,
    task_type TEXT NOT NULL,
    product TEXT DEFAULT '',
    raw_text TEXT DEFAULT '',
    summary_id TEXT DEFAULT '',
    params JSONB DEFAULT '{}',
    platform TEXT DEFAULT '',
    result_artifacts_count INTEGER NOT NULL DEFAULT 0,
    result_status TEXT DEFAULT '',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 品牌风格（资产层持久化，单条全局风格）
CREATE TABLE IF NOT EXISTS brand_styles (
    id BIGSERIAL PRIMARY KEY,
    style_id TEXT NOT NULL UNIQUE,
    keywords JSONB DEFAULT '[]',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========== 种子数据 ==========

-- 商品
INSERT INTO products (name, category, price, cost, stock, status) VALUES
('北欧简约沙发', '家具', 2899, 1800, 45, 'on_sale'),
('复古黄铜吊灯', '灯具', 599, 320, 28, 'on_sale'),
('日式棉麻抱枕', '软装', 89, 35, 156, 'on_sale'),
('实木茶几', '家具', 1299, 780, 12, 'on_sale'),
('ins风装饰画', '装饰', 159, 60, 0, 'out_of_stock'),
('手工编织地毯', '软装', 899, 450, 8, 'on_sale'),
('香薰蜡烛套装', '生活', 199, 80, 67, 'on_sale'),
('陶瓷餐具六件套', '餐厨', 329, 140, 23, 'on_sale');

-- 每日统计（最近7天）
INSERT INTO daily_stats (stat_date, gmv, orders, visitors, conversion_rate) VALUES
('2026-07-17', 9200, 62, 2100, 3.0),
('2026-07-18', 8500, 55, 1950, 2.8),
('2026-07-19', 11000, 72, 2800, 2.6),
('2026-07-20', 7800, 48, 1850, 2.6),
('2026-07-21', 10200, 68, 2400, 2.8),
('2026-07-22', 9500, 60, 2200, 2.7),
('2026-07-23', 12580, 86, 2680, 3.2);

-- AI 任务
INSERT INTO ai_tasks (task_type, product, params, status, cost, completed_at) VALUES
('image_gen', '北欧简约沙发', '{"image_type":"main","quantity":4}', 'done', 8, now()),
('copywriting', '日式棉麻抱枕', '{"type":"title"}', 'done', 2, now()),
('image_gen', '复古黄铜吊灯', '{"image_type":"scene","quantity":2}', 'done', 4, now()),
('image_gen', '陶瓷餐具六件套', '{"image_type":"detail","quantity":6}', 'done', 12, now()),
('copywriting', '香薰蜡烛套装', '{"type":"xiaohongshu"}', 'done', 2, now());

-- 素材库
INSERT INTO assets (asset_type, product_name) VALUES
('main', '北欧简约沙发'),
('main', '北欧简约沙发'),
('scene', '复古黄铜吊灯'),
('scene', '复古黄铜吊灯'),
('detail', '陶瓷餐具六件套'),
('detail', '陶瓷餐具六件套'),
('poster', '香薰蜡烛套装'),
('carousel', '日式棉麻抱枕'),
('main', '手工编织地毯');

-- 营销活动
INSERT INTO campaigns (name, type, start_date, end_date, status, discount_value, conditions) VALUES
('夏日清仓特卖', 'flash_sale', '2026-07-01', '2026-07-31', 'active', 50, '全场满200减50'),
('新品上市优惠', 'full_reduction', '2026-07-15', '2026-08-15', 'active', 30, '满500减30'),
('开学季大促', 'group_buy', '2026-08-01', '2026-08-20', 'upcoming', 20, '3人成团享8折'),
('新人专享礼', 'new_user', '2026-06-01', '2026-12-31', 'active', 15, '首单立减15元');

-- 优惠券
INSERT INTO coupons (name, type, value, condition_amount, claimed_count, total_count, status) VALUES
('满200减50', 'full_reduction', 50, 200, 78, 100, 'active'),
('9折优惠券', 'discount', 10, 0, 45, 200, 'active'),
('新人15元券', 'new_user', 15, 0, 156, 500, 'active');

-- 客服消息
INSERT INTO customer_messages (customer_name, message_preview, unread_count, status) VALUES
('张小姐', '沙发有现货吗？什么时候能发货？', 2, 'pending'),
('李先生', '吊灯安装麻烦吗？包安装吗？', 1, 'pending'),
('王女士', '抱枕可以机洗吗？', 3, 'pending'),
('赵先生', '地毯尺寸有1.5m的吗？', 1, 'pending'),
('陈小姐', '餐具套装包含哪些？', 0, 'resolved');

-- FAQ
INSERT INTO faq (question, answer, category, sort_order) VALUES
('发货时间是多久？', '现货商品24小时内发货，定制商品3-5个工作日发货。', '物流', 0),
('支持哪些支付方式？', '支持微信、支付宝、银行卡转账，企业用户支持对公转账。', '支付', 1),
('退换货政策是什么？', '7天无理由退换货，商品质量问题运费由我们承担。', '售后', 2),
('可以开发票吗？', '可以开具电子发票和纸质发票，下单时备注即可。', '发票', 3),
('有实体店吗？', '我们在杭州有一家体验店，欢迎来店体验。', '其他', 4);

-- 财务记录
INSERT INTO finance_records (record_type, category, amount, description, record_date) VALUES
('income', '商品销售收入', 45800, '7月商品销售', '2026-07'),
('expense', '平台佣金', 6870, '各平台佣金扣点', '2026-07'),
('expense', '广告投放', 5200, '直通车+信息流广告', '2026-07'),
('expense', '物流仓储', 3500, '快递+仓库租赁', '2026-07'),
('expense', '素材制作', 2630, 'AI出图+摄影外包', '2026-07'),
('income', '商品销售收入', 38200, '6月商品销售', '2026-06'),
('expense', '平台佣金', 5730, '6月各平台佣金', '2026-06'),
('expense', '广告投放', 4100, '6月广告投放', '2026-06'),
('income', '商品销售收入', 41500, '5月商品销售', '2026-05'),
('expense', '平台佣金', 6225, '5月平台佣金', '2026-05'),
('income', '商品销售收入', 35800, '4月商品销售', '2026-04'),
('expense', '平台佣金', 5370, '4月平台佣金', '2026-04');

-- ========== 启用 RLS（可选，demo 阶段可跳过） ==========
-- 如需行级安全，取消注释以下语句并创建 policy
-- ALTER TABLE products ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "允许全部操作" ON products FOR ALL USING (true) WITH CHECK (true);
