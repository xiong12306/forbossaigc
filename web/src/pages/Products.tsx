import { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Package,
  Plus,
  Search,
  Edit3,
  ArrowDownToLine,
  ArrowUpFromLine,
  Boxes,
  Loader2,
} from "lucide-react";
import { productsApi } from "@/platformApi";

type Status = "on_sale" | "out_of_stock" | "off_shelf";

interface Product {
  id: number;
  name: string;
  category: string;
  price: number;
  cost: number;
  stock: number;
  status: Status;
  image_url: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

const STATUS_META: Record<Status, { label: string; cls: string; dot: string }> = {
  on_sale: {
    label: "在售",
    cls: "text-gold-300 bg-gold-500/10 border-gold-500/30",
    dot: "bg-gold-400",
  },
  out_of_stock: {
    label: "缺货",
    cls: "text-terracotta-400 bg-terracotta-500/10 border-terracotta-500/30",
    dot: "bg-terracotta-500",
  },
  off_shelf: {
    label: "下架",
    cls: "text-ivory-400/60 bg-brown-800/60 border-brown-700/60",
    dot: "bg-ivory-400/40",
  },
};

// 商品图渐变占位（按 id 取模分配，保持视觉差异）
const GRADIENTS = [
  "from-gold-500 to-terracotta-500",
  "from-gold-400 to-gold-600",
  "from-terracotta-400 to-brown-700",
  "from-brown-700 to-charcoal-900",
  "from-ivory-400 to-gold-500",
  "from-gold-300 to-terracotta-400",
  "from-terracotta-500 to-brown-800",
  "from-brown-800 to-charcoal-900",
];

function gradientFor(id: number) {
  return GRADIENTS[id % GRADIENTS.length];
}

export default function Products() {
  const [keyword, setKeyword] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);

  const fetchProducts = async (search?: string) => {
    setLoading(true);
    try {
      const data = await productsApi.list(search);
      setProducts(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("获取商品列表失败:", e);
      setProducts([]);
    } finally {
      setLoading(false);
    }
  };

  // 搜索框输入触发请求（带 debounce），同时处理初次加载
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchProducts(keyword.trim() || undefined);
    }, keyword ? 350 : 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keyword]);

  const handleToggleStatus = async (p: Product) => {
    if (actionLoadingId !== null) return;
    const nextStatus: Status = p.status === "on_sale" ? "off_shelf" : "on_sale";
    setActionLoadingId(p.id);
    try {
      await productsApi.updateStatus(p.id, nextStatus);
      // 刷新列表
      await fetchProducts(keyword.trim() || undefined);
    } catch (e) {
      console.error("更新商品状态失败:", e);
    } finally {
      setActionLoadingId(null);
    }
  };

  // 统计
  const stats = useMemo(() => {
    const onSale = products.filter((p) => p.status === "on_sale").length;
    const outStock = products.filter((p) => p.status === "out_of_stock").length;
    const totalStock = products.reduce((sum, p) => sum + (p.stock || 0), 0);
    return { onSale, outStock, totalStock };
  }, [products]);

  return (
    <div className="min-h-full p-4 lg:p-6 text-ivory-500">
      <div className="max-w-7xl mx-auto">
        {/* 顶部工具栏 */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex items-center justify-end mb-6"
        >
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 text-sm font-medium shadow-gold-glow transition"
          >
            <Plus className="w-4 h-4" />
            添加商品
          </motion.button>
        </motion.div>

        {/* 搜索框 */}
        <div className="mb-6">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-ivory-400/40" />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索商品名称、分类或编号..."
              className="w-full pl-11 pr-4 py-3 rounded-xl bg-brown-800/60 border border-gold-500/20 text-ivory-500 placeholder-ivory-400/40 focus:outline-none focus:border-gold-500/60 focus:ring-1 focus:ring-gold-500/30 transition"
            />
          </div>
        </div>

        {/* 加载状态 */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-gold-400 animate-spin mb-3" />
            <div className="text-sm text-ivory-400/60">加载商品列表中...</div>
          </div>
        )}

        {/* 表头 + 商品列表（宽表格横向滚动） */}
        {!loading && (
          <div className="overflow-x-auto -mx-4 px-4 lg:mx-0 lg:px-0">
          <div className="min-w-[720px] lg:min-w-0">
          {/* 表头 */}
          <div className="grid grid-cols-12 gap-4 px-5 py-3 mb-2 rounded-xl bg-brown-900/70 border border-brown-700/50 text-xs text-ivory-400/60 tracking-wider uppercase">
            <div className="col-span-1">商品图</div>
            <div className="col-span-4">商品名称</div>
            <div className="col-span-2">价格</div>
            <div className="col-span-2">库存</div>
            <div className="col-span-2">状态</div>
            <div className="col-span-1 text-right">操作</div>
          </div>

          <div className="space-y-2">
            {products.map((p, idx) => {
              const meta = STATUS_META[p.status] || STATUS_META.off_shelf;
              const isActioning = actionLoadingId === p.id;
              return (
                <motion.div
                  key={p.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: idx * 0.04 }}
                  whileHover={{ scale: 1.005 }}
                  className="grid grid-cols-12 gap-4 items-center px-5 py-3.5 rounded-xl bg-charcoal-800/60 border border-brown-700/40 hover:border-gold-500/40 hover:bg-charcoal-800 transition-all"
                >
                  {/* 商品图（渐变占位） */}
                  <div className="col-span-1">
                    <div
                      className={`w-12 h-12 rounded-lg bg-gradient-to-br ${gradientFor(p.id)} flex items-center justify-center shadow-warm-glow overflow-hidden`}
                    >
                      {p.image_url ? (
                        <img
                          src={p.image_url}
                          alt={p.name}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = "none";
                          }}
                        />
                      ) : (
                        <Boxes className="w-5 h-5 text-charcoal-900/80" />
                      )}
                    </div>
                  </div>
                  {/* 名称 */}
                  <div className="col-span-4 min-w-0">
                    <div className="text-sm text-ivory-500 font-medium truncate">{p.name}</div>
                    <div className="text-xs text-ivory-400/50 mt-0.5">
                      <span className="font-mono">#{p.id}</span> · {p.category}
                    </div>
                  </div>
                  {/* 价格 */}
                  <div className="col-span-2">
                    <span className="text-sm font-serif text-gold-300">
                      ¥{Number(p.price || 0).toLocaleString()}
                    </span>
                  </div>
                  {/* 库存 */}
                  <div className="col-span-2">
                    <span
                      className={`text-sm ${
                        p.stock === 0
                          ? "text-terracotta-400"
                          : p.stock < 10
                          ? "text-gold-400"
                          : "text-ivory-500"
                      }`}
                    >
                      {p.stock}
                    </span>
                    <span className="text-xs text-ivory-400/40 ml-1">件</span>
                  </div>
                  {/* 状态标签 */}
                  <div className="col-span-2">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border ${meta.cls}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                      {meta.label}
                    </span>
                  </div>
                  {/* 操作 */}
                  <div className="col-span-1 flex items-center justify-end gap-1">
                    <button
                      title="编辑"
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-ivory-400/70 hover:text-gold-300 hover:bg-gold-500/10 transition"
                    >
                      <Edit3 className="w-4 h-4" />
                    </button>
                    {isActioning ? (
                      <div className="w-8 h-8 flex items-center justify-center">
                        <Loader2 className="w-4 h-4 text-gold-400 animate-spin" />
                      </div>
                    ) : p.status === "on_sale" ? (
                      <button
                        title="下架"
                        onClick={() => handleToggleStatus(p)}
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-ivory-400/70 hover:text-terracotta-400 hover:bg-terracotta-500/10 transition"
                      >
                        <ArrowDownToLine className="w-4 h-4" />
                      </button>
                    ) : (
                      <button
                        title="上架"
                        onClick={() => handleToggleStatus(p)}
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-ivory-400/70 hover:text-gold-300 hover:bg-gold-500/10 transition"
                      >
                        <ArrowUpFromLine className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </motion.div>
              );
            })}

            {products.length === 0 && (
              <div className="text-center py-16 text-ivory-400/40 text-sm">
                没有找到匹配的商品
              </div>
            )}
          </div>
          </div>
          </div>
        )}
      </div>
    </div>
  );
}
