/**
 * AI 新闻调取平台 — 主逻辑 v2
 * GSAP 动画编排 · 状态机驱动 · 零框架依赖
 */

const API_BASE = "http://127.0.0.1:8000/api";

// ═══════════════════════════════════════════════════
// DOM 引用
// ═══════════════════════════════════════════════════
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
    currentDate: $("#currentDate"),
    btnFetch: $("#btnFetch"),
    btnSettings: $("#btnSettings"),
    currentLLM: $("#currentLLM"),
    historyTree: $("#historyTree"),
    stateEmpty: $("#stateEmpty"),
    stateLoading: $("#stateLoading"),
    stateLoaded: $("#stateLoaded"),
    stateError: $("#stateError"),
    loadingDetail: $("#loadingDetail"),
    sourceBadgeNewsAPI: $("#sourceBadgeNewsAPI"),
    sourceBadgeGitHub: $("#sourceBadgeGitHub"),
    resultBadge: $("#resultBadge"),
    newsList: $("#newsList"),
    btnViewRecord: $("#btnViewRecord"),
    errorMessage: $("#errorMessage"),
    modalOverlay: $("#modalOverlay"),
    modalPanel: $("#modalPanel"),
    modalTitle: $("#modalTitle"),
    modalBody: $("#modalBody"),
    btnModalClose: $("#btnModalClose"),
    toastContainer: $("#toastContainer"),
};

// ═══════════════════════════════════════════════════
// 状态管理
// ═══════════════════════════════════════════════════
const state = {
    currentDate: new Date().toISOString().split("T")[0],
    newsData: null,
    status: "IDLE", // IDLE | LOADING | LOADED | ERROR
    selectedCategory: null, // null = 全部, 否则为分类名
};

// ═══════════════════════════════════════════════════
// GSAP 动画系统
// ═══════════════════════════════════════════════════
const Anim = {
    // 全局默认值
    defaults: { duration: 0.4, ease: "power3.out" },

    /**
     * 页面初始加载动画
     * 时间线：顶栏 → 侧边栏 → 内容区 → 按钮弹入
     */
    pageLoad() {
        gsap.defaults({ ease: "power3.out" });

        const tl = gsap.timeline();

        tl.from(".top-bar", { y: -64, opacity: 0, duration: 0.55 })
          .from(".sidebar", { x: -36, opacity: 0, duration: 0.45 }, "-=0.3")
          .from(".empty-icon-wrapper", { scale: 0.6, opacity: 0, duration: 0.5, ease: "back.out(1.8)" }, "-=0.2")
          .from(".empty-title", { y: 16, opacity: 0, duration: 0.35 }, "-=0.25")
          .from(".empty-desc", { y: 12, opacity: 0, duration: 0.35 }, "-=0.2")
          .from(".empty-features span", {
              y: 10,
              opacity: 0,
              stagger: 0.06,
              duration: 0.35,
              ease: "back.out(1.4)",
          }, "-=0.15")
          .from(".btn-fetch", { scale: 0.7, opacity: 0, duration: 0.45, ease: "elastic.out(1, 0.6)" }, "-=0.2");

        // 初始状态下按钮脉冲
        this.buttonIdlePulse();
    },

    /**
     * 查询按钮空闲脉冲
     */
    buttonIdlePulse() {
        dom.btnFetch.classList.add("idle-pulse");
    },

    /**
     * 按钮按下反馈
     */
    buttonPress(target) {
        gsap.to(target, { scale: 0.95, duration: 0.1, ease: "power2.in" });
        gsap.to(target, { scale: 1, duration: 0.25, ease: "elastic.out(1, 0.5)", delay: 0.1 });
    },

    /**
     * 状态切换：IDLE → LOADING
     */
    stateToLoading() {
        dom.btnFetch.classList.remove("idle-pulse");

        const tl = gsap.timeline();

        // 淡出当前状态
        tl.to(dom.stateEmpty, { opacity: 0, scale: 0.96, duration: 0.25, ease: "power2.in" });
        tl.set(dom.stateEmpty, { display: "none" });
        tl.set(dom.stateLoading, { display: "block", opacity: 0, scale: 0.98 });

        // 淡入加载状态
        tl.to(dom.stateLoading, { opacity: 1, scale: 1, duration: 0.35, ease: "power3.out" });

        // 旋转动画
        gsap.to(".loader-ring", { rotation: 360, duration: 1.2, repeat: -1, ease: "none" });

        // 加载点脉动
        gsap.to(".loader-dot", { scale: 1.6, duration: 0.6, repeat: -1, yoyo: true, ease: "power1.inOut" });

        // 来源标签渐显
        gsap.fromTo([dom.sourceBadgeNewsAPI, dom.sourceBadgeGitHub],
            { opacity: 0, y: 8 },
            { opacity: 0.5, y: 0, stagger: 0.2, duration: 0.35 }
        );

        return tl;
    },

    /**
     * 状态切换：LOADING → LOADED，带新闻卡片 stagger
     */
    stateToLoaded(newsData) {
        gsap.killTweensOf(".loader-ring");
        gsap.killTweensOf(".loader-dot");

        const tl = gsap.timeline();

        // 切换状态容器
        tl.to(dom.stateLoading, { opacity: 0, scale: 0.96, duration: 0.2, ease: "power2.in" });
        tl.set(dom.stateLoading, { display: "none" });
        tl.set(dom.stateLoaded, { display: "block", opacity: 0 });
        tl.to(dom.stateLoaded, { opacity: 1, duration: 0.35, ease: "power3.out" });

        // 结果头部
        tl.from(dom.resultBadge, { x: -20, opacity: 0, duration: 0.35, ease: "back.out(1.4)" }, "-=0.15");
        tl.from(dom.btnViewRecord, { x: 20, opacity: 0, duration: 0.35, ease: "back.out(1.4)" }, "-=0.25");

        // 新闻卡片 stagger 入场
        tl.from(".news-card", {
            y: 48,
            opacity: 0,
            scale: 0.94,
            stagger: 0.06,
            duration: 0.5,
            ease: "power3.out",
        }, "-=0.1");

        return tl;
    },

    /**
     * 状态切换：LOADING → ERROR
     */
    stateToError(message) {
        gsap.killTweensOf(".loader-ring");
        gsap.killTweensOf(".loader-dot");

        const tl = gsap.timeline();

        tl.to(dom.stateLoading, { opacity: 0, scale: 0.96, duration: 0.2, ease: "power2.in" });
        tl.set(dom.stateLoading, { display: "none" });
        tl.set(dom.stateError, { display: "block", opacity: 0 });

        // 错误图标震动
        tl.to(dom.stateError, { opacity: 1, duration: 0.3 });
        tl.from(".error-icon-wrapper", { scale: 0, duration: 0.5, ease: "back.out(2)" }, "-=0.2");
        tl.from(".error-message", { y: 10, opacity: 0, duration: 0.3 }, "-=0.2");
        tl.from(".btn-retry", { y: 10, opacity: 0, duration: 0.3, ease: "back.out(1.4)" }, "-=0.15");

        // 错误震动
        gsap.to(".error-icon-wrapper", {
            x: [-8, 8, -6, 6, -3, 3, 0],
            duration: 0.6,
            ease: "power2.out",
            delay: 0.3,
        });

        return tl;
    },

    /**
     * 切换为缓存数据（直接切到 LOADED 状态无加载动画）
     */
    stateToCached(newsData) {
        const tl = gsap.timeline();

        tl.to(dom.stateEmpty, { opacity: 0, scale: 0.96, duration: 0.2, ease: "power2.in" });
        tl.set(dom.stateEmpty, { display: "none" });
        tl.set(dom.stateLoaded, { display: "block", opacity: 0 });
        tl.to(dom.stateLoaded, { opacity: 1, duration: 0.3, ease: "power3.out" });

        tl.from(dom.resultBadge, { x: -20, opacity: 0, duration: 0.35, ease: "back.out(1.4)" }, "-=0.1");
        tl.from(".news-card", {
            y: 40,
            opacity: 0,
            scale: 0.95,
            stagger: 0.05,
            duration: 0.45,
            ease: "power3.out",
        }, "-=0.05");

        return tl;
    },

    /**
     * 新闻卡片 hover 微动效
     */
    cardHoverIn(card) {
        gsap.to(card, { y: -2, scale: 1.01, duration: 0.25, ease: "power2.out" });
    },
    cardHoverOut(card) {
        gsap.to(card, { y: 0, scale: 1, duration: 0.25, ease: "power2.out" });
    },

    /**
     * 模态框打开
     * 弹性缩放 + 背景淡入
     */
    modalOpen() {
        dom.modalOverlay.style.display = "flex";

        const tl = gsap.timeline();

        tl.fromTo(dom.modalOverlay, { opacity: 0 }, { opacity: 1, duration: 0.25 });
        tl.fromTo(dom.modalPanel,
            { scale: 0.82, opacity: 0, y: 30 },
            { scale: 1, opacity: 1, y: 0, duration: 0.5, ease: "elastic.out(1, 0.55)" },
            "-=0.15"
        );

        return tl;
    },

    /**
     * 模态框关闭
     * @param {Function} onComplete 动画完成后的回调
     */
    modalClose(onComplete) {
        const tl = gsap.timeline({
            onComplete: () => {
                dom.modalOverlay.style.display = "none";
                if (onComplete) onComplete();
            }
        });

        tl.to(dom.modalPanel,
            { scale: 0.92, opacity: 0, y: 16, duration: 0.22, ease: "power2.in" }
        );
        tl.to(dom.modalOverlay, { opacity: 0, duration: 0.18, ease: "power2.in" }, "-=0.12");

        return tl;
    },

    /**
     * 历史树展开 — 用 GSAP 动画高度变化
     */
    treeExpand(container) {
        const targetHeight = container.scrollHeight;
        gsap.fromTo(container,
            { height: 0, opacity: 0 },
            { height: targetHeight, opacity: 1, duration: 0.35, ease: "power3.out" }
        );
    },

    /**
     * 历史树折叠
     */
    treeCollapse(container, onComplete) {
        gsap.to(container, {
            height: 0,
            opacity: 0,
            duration: 0.25,
            ease: "power2.in",
            onComplete: () => {
                if (onComplete) onComplete();
            },
        });
    },

    /**
     * 历史记录的日期项 stagger 入场
     */
    treeDaysEntrance(dayList) {
        gsap.from(dayList.children, {
            x: -12,
            opacity: 0,
            stagger: 0.03,
            duration: 0.3,
            ease: "power3.out",
        });
    },

    /**
     * Toast 弹出通知
     * @param {'success'|'error'|'info'} type
     */
    toast(message, type = "info") {
        const emojiMap = { success: "✅", error: "❌", info: "ℹ️" };
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-emoji">${emojiMap[type]}</span>
            <span>${escapeHtml(message)}</span>
        `;

        dom.toastContainer.appendChild(toast);

        // 入场：从右侧滑入 + 弹性
        gsap.fromTo(toast,
            { x: 100, opacity: 0, scale: 0.9 },
            { x: 0, opacity: 1, scale: 1, duration: 0.45, ease: "elastic.out(1, 0.6)" }
        );

        // 自动移除
        gsap.to(toast, {
            x: 80,
            opacity: 0,
            scale: 0.9,
            duration: 0.3,
            ease: "power2.in",
            delay: 3.2,
            onComplete: () => toast.remove(),
        });
    },

    /**
     * 加载进度指示 — 逐一点亮来源标签
     */
    sourceActive(badge) {
        gsap.to(badge, { opacity: 1, scale: 1.05, duration: 0.3, ease: "power2.out" });
        badge.classList.add("active");
    },
    sourceDone(badge) {
        gsap.to(badge, { scale: 1, duration: 0.3, ease: "back.out(1.4)" });
        badge.classList.remove("active");
        badge.classList.add("done");
    },

    /**
     * 按钮加载状态
     */
    buttonLoading(btn) {
        gsap.to(btn, { scale: 0.96, duration: 0.15, ease: "power2.in" });
    },
    buttonNormal(btn) {
        gsap.to(btn, { scale: 1, duration: 0.25, ease: "elastic.out(1, 0.5)" });
    },
};

// ═══════════════════════════════════════════════════
// 初始化
// ═══════════════════════════════════════════════════
document.addEventListener("DOMContentLoaded", () => {
    // 格式化日期
    const today = new Date();
    dom.currentDate.textContent = `— ${today.toLocaleDateString("zh-CN", {
        year: "numeric", month: "long", day: "numeric",
    })}`;

    // 页面加载动画
    Anim.pageLoad();

    // 事件绑定
    dom.btnFetch.addEventListener("click", () => {
        state.selectedCategory = null; // 主按钮重置分类过滤
        updateCategoryTags();
        Anim.buttonPress(dom.btnFetch);
        fetchNews();
    });
    dom.btnViewRecord.addEventListener("click", () => viewRecord());
    dom.btnModalClose.addEventListener("click", () => Anim.modalClose());
    dom.modalOverlay.addEventListener("click", (e) => {
        if (e.target === dom.modalOverlay) Anim.modalClose();
    });

    // 键盘 ESC 关闭模态框
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && dom.modalOverlay.style.display === "flex") {
            Anim.modalClose();
        }
    });

    // 分类标签点击 — 触发抓取 + 分类过滤
    $$(".empty-features span").forEach((tag) => {
        tag.style.cursor = "pointer";
        tag.addEventListener("click", () => {
            const category = tag.textContent.replace(/^[^\s]+\s*/, ""); // 去掉emoji和空格
            state.selectedCategory = state.selectedCategory === category ? null : category;
            updateCategoryTags();
            $$(".empty-features span").forEach(t => t.classList.remove("active"));
            if (state.selectedCategory) tag.classList.add("active");
            fetchNews();
        });
    });

    // 加载历史记录树
    loadHistory();
});

// ═══════════════════════════════════════════════════
// 新闻抓取
// ═══════════════════════════════════════════════════
async function fetchNews() {
    if (state.status === "LOADING") return;

    // 进入加载状态
    state.status = "LOADING";
    dom.btnFetch.disabled = true;
    dom.btnFetch.innerHTML = '<span class="btn-icon">⏳</span><span>抓取中...</span>';
    Anim.buttonLoading(dom.btnFetch);
    Anim.stateToLoading();

    // 模拟阶段提示
    const stages = [
        { text: "连接 NewsAPI...", badge: dom.sourceBadgeNewsAPI },
        { text: "搜索 GitHub Trending...", badge: dom.sourceBadgeGitHub },
        { text: "正在整理排序...", badge: null },
    ];

    let stageIdx = 0;
    const stageInterval = setInterval(() => {
        if (stageIdx > 0 && stages[stageIdx - 1].badge) {
            Anim.sourceDone(stages[stageIdx - 1].badge);
        }
        if (stageIdx < stages.length) {
            dom.loadingDetail.textContent = stages[stageIdx].text;
            if (stages[stageIdx].badge) {
                Anim.sourceActive(stages[stageIdx].badge);
            }
            stageIdx++;
        }
    }, 800);

    try {
        const resp = await fetch(`${API_BASE}/news/fetch`);
        const data = await resp.json();
        clearInterval(stageInterval);

        if (!resp.ok) {
            throw new Error(data.detail || `请求失败 (HTTP ${resp.status})`);
        }

        state.newsData = data;
        state.currentDate = data.date;

        if (data.count === 0) {
            state.status = "ERROR";
            Anim.stateToError(data.message || "今日未获取到 AI 相关新闻");
            dom.btnFetch.disabled = false;
            dom.btnFetch.innerHTML = '<span class="btn-icon">🔄</span><span>重试</span>';
            Anim.buttonNormal(dom.btnFetch);
            return;
        }

        // 加载成功
        state.status = "LOADED";

        // 标记所有来源完成
        Anim.sourceDone(dom.sourceBadgeNewsAPI);
        Anim.sourceDone(dom.sourceBadgeGitHub);

        renderNewsList(data);
        dom.resultBadge.textContent = data.cached
            ? `📦 缓存 · ${data.count} 条精选`
            : `🆕 共 ${data.total_fetched} 条 · 精选 ${data.count} 条`;

        await Anim.stateToLoaded(data);

        dom.btnFetch.disabled = false;
        dom.btnFetch.innerHTML = '<span class="btn-icon">🔄</span><span>刷新新闻</span>';
        Anim.buttonNormal(dom.btnFetch);

        // 刷新历史树
        loadHistory();

    } catch (err) {
        clearInterval(stageInterval);
        state.status = "ERROR";
        dom.errorMessage.textContent = err.message;
        Anim.stateToError(err.message);

        dom.btnFetch.disabled = false;
        dom.btnFetch.innerHTML = '<span class="btn-icon">🔄</span><span>重试</span>';
        Anim.buttonNormal(dom.btnFetch);
    }
}

// ═══════════════════════════════════════════════════
// 新闻列表渲染
// ═══════════════════════════════════════════════════
function renderNewsList(data) {
    dom.newsList.innerHTML = "";

    // ── 分类过滤条 ──
    const categories = ["全部", "新功能发布", "新平台上线", "好用工具", "GitHub项目"];
    const emojiMap = { "新功能发布": "🔬", "新平台上线": "🚀", "好用工具": "🛠", "GitHub项目": "📦" };
    const counts = {};
    categories.forEach(c => { counts[c] = 0; });
    data.news.forEach(n => {
        const c = n.category || "AI新闻";
        if (counts[c] !== undefined) counts[c]++;
        else if (counts["全部"] !== undefined) counts["全部"]++; // fallback
    });
    counts["全部"] = data.news.length;

    const filterBar = document.createElement("div");
    filterBar.className = "category-filter-bar";
    categories.forEach(cat => {
        const pill = document.createElement("span");
        pill.className = "filter-pill";
        if ((cat === "全部" && !state.selectedCategory) || cat === state.selectedCategory) {
            pill.classList.add("active");
        }
        const emoji = emojiMap[cat] || "";
        pill.innerHTML = `${emoji} ${cat} <small>(${counts[cat] || 0})</small>`;
        pill.addEventListener("click", (e) => {
            e.stopPropagation();
            state.selectedCategory = cat === "全部" ? null : cat;
            renderNewsList(data);
            // 重新 stagger 入场
            gsap.from(".news-card", {
                y: 48, opacity: 0, scale: 0.94,
                stagger: 0.06, duration: 0.5, ease: "power3.out",
            });
        });
        filterBar.appendChild(pill);
    });
    dom.newsList.appendChild(filterBar);

    // ── 过滤 ──
    const filtered = state.selectedCategory
        ? data.news.filter(n => (n.category || "AI新闻") === state.selectedCategory)
        : data.news;

    if (filtered.length === 0) {
        const empty = document.createElement("p");
        empty.style.cssText = "text-align:center;color:var(--text-secondary);padding:32px;";
        empty.textContent = `该分类下暂无新闻`;
        dom.newsList.appendChild(empty);
        return;
    }

    // ── 新闻卡片 ──
    filtered.forEach((item) => {
        const card = document.createElement("div");
        card.className = "news-card";

        // 点击跳转原文
        card.addEventListener("click", () => window.open(item.url, "_blank"));

        // Hover 微动效
        card.addEventListener("mouseenter", () => Anim.cardHoverIn(card));
        card.addEventListener("mouseleave", () => Anim.cardHoverOut(card));

        const hotnessClass = item.hotness >= 80 ? "hotness-high"
            : item.hotness >= 50 ? "hotness-mid" : "hotness-low";

        const cnSummary = item.summary_cn || "";
        const enSummary = item.summary || "暂无简述";
        // 有中文摘要时，中文为主、英文为辅；否则回退英文
        const primarySummary = cnSummary || enSummary;
        const secondarySummary = cnSummary ? enSummary : "";

        card.innerHTML = `
            <div class="news-card-header">
                <div style="flex:1;min-width:0;">
                    <div class="news-card-title">${escapeHtml(item.title)}</div>
                    <div class="news-card-summary ${cnSummary ? 'summary-cn' : ''}">${escapeHtml(primarySummary)}</div>
                    ${secondarySummary ? `<div class="news-card-summary-en">${escapeHtml(secondarySummary)}</div>` : ""}
                    <div class="news-card-meta">
                        <span class="news-tag tag-source">${escapeHtml(item.source)}</span>
                        <span class="news-tag tag-category">${escapeHtml(item.category)}</span>
                        <a href="${escapeHtml(item.url)}" target="_blank"
                           class="news-link" onclick="event.stopPropagation();">
                           🔗 查看原文
                        </a>
                    </div>
                </div>
                <div class="news-hotness ${hotnessClass}">
                    ⭐${Math.round(item.hotness)}
                </div>
            </div>
        `;

        dom.newsList.appendChild(card);
    });
}

// ── 更新主页分类标签高亮 ──
function updateCategoryTags() {
    $$(".empty-features span").forEach(tag => {
        const cat = tag.textContent.replace(/^[^\s]+\s*/, "");
        tag.style.background = state.selectedCategory === cat
            ? "var(--primary)"
            : "";
        tag.style.color = state.selectedCategory === cat ? "#fff" : "";
    });
}

// ═══════════════════════════════════════════════════
// 查看记录本（模态框）
// ═══════════════════════════════════════════════════
async function viewRecord() {
    if (!state.newsData) return;

    dom.modalTitle.textContent = `📝 加载中...`;
    dom.modalBody.innerHTML = `
        <div class="loader" style="width:36px;height:36px;">
            <div class="loader-ring" style="border-width:2px;"></div>
        </div>
        <p style="text-align:center;color:var(--text-secondary);">加载记录本...</p>
    `;

    await Anim.modalOpen();

    // 加载器旋转
    gsap.to(".modal-body .loader-ring", { rotation: 360, duration: 1, repeat: -1, ease: "none" });

    try {
        const resp = await fetch(`${API_BASE}/records?date=${state.currentDate}`);
        const data = await resp.json();

        gsap.killTweensOf(".modal-body .loader-ring");

        if (!resp.ok) throw new Error(data.detail || "加载失败");

        dom.modalTitle.textContent = `📝 AI 新闻日报 — ${state.currentDate}`;

        let markdown = "";
        if (data.source === "file" && data.markdown) {
            markdown = data.markdown;
        } else if (data.news) {
            const lines = [
                `# 🤖 AI 新闻日报 — ${state.currentDate}`,
                "",
                `> 共 ${data.count} 条新闻 | ${state.currentDate}`,
                "",
            ];
            const cats = {};
            data.news.forEach((n) => {
                const c = n.category || "AI新闻";
                if (!cats[c]) cats[c] = [];
                cats[c].push(n);
            });
            const emoji = { "新功能发布": "🔥", "新平台上线": "🚀", "好用工具": "🛠", "GitHub项目": "📦" };
            for (const [cat, items] of Object.entries(cats)) {
                lines.push(`## ${emoji[cat] || "📌"} ${cat}`);
                lines.push("");
                items.forEach((n, i) => {
                    lines.push(`${i + 1}. **[${escapeHtml(n.title)}](${n.url})** — ${escapeHtml(n.summary || "")} ⭐${Math.round(n.hotness)}`);
                });
                lines.push("");
            }
            markdown = lines.join("\n");
        }

        // 带过渡的 Markdown 渲染
        dom.modalBody.style.opacity = "0";
        dom.modalBody.style.transform = "translateY(12px)";
        dom.modalBody.innerHTML = `<div class="markdown-body">${marked.parse(markdown)}</div>`;

        gsap.to(dom.modalBody, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out" });

    } catch (err) {
        dom.modalBody.innerHTML = `<p style="color:var(--accent-red);text-align:center;">加载失败: ${err.message}</p>`;
    }
}

function closeModal() {
    Anim.modalClose();
}

// ═══════════════════════════════════════════════════
// 历史记录树
// ═══════════════════════════════════════════════════
async function loadHistory() {
    try {
        const resp = await fetch(`${API_BASE}/records/history`);
        const data = await resp.json();

        if (!resp.ok || !Array.isArray(data) || data.length === 0) {
            dom.historyTree.innerHTML = '<p class="empty-hint">暂无历史记录</p>';
            gsap.from(dom.historyTree, { opacity: 0, y: 10, duration: 0.4 });
            return;
        }

        renderHistoryTree(data);
    } catch {
        dom.historyTree.innerHTML = '<p class="empty-hint">加载失败</p>';
    }
}

function renderHistoryTree(tree) {
    dom.historyTree.innerHTML = "";

    tree.forEach((yearNode, yi) => {
        const yearGroup = document.createElement("div");
        yearGroup.className = "year-group";

        const yearLabel = document.createElement("div");
        yearLabel.className = "year-label";
        yearLabel.textContent = `▶ ${yearNode.year}年`;

        const monthsContainer = document.createElement("div");
        monthsContainer.className = "months";
        monthsContainer.style.display = "none";

        yearNode.months.forEach((monthNode) => {
            const monthGroup = document.createElement("div");
            monthGroup.className = "month-group";

            const monthLabel = document.createElement("div");
            monthLabel.className = "month-label";
            monthLabel.textContent = `▶ ${monthNode.month}月`;

            const dayList = document.createElement("div");
            dayList.className = "day-list";

            monthNode.days.forEach((day) => {
                const dateStr = `${yearNode.year}-${monthNode.month}-${day}`;
                const dayItem = document.createElement("div");
                dayItem.className = "day-item has-record";
                dayItem.textContent = `📄 ${day}`;
                dayItem.addEventListener("click", () =>
                    loadDayRecord(dateStr, dayItem)
                );
                dayList.appendChild(dayItem);
            });

            // 展开/折叠月份
            monthLabel.addEventListener("click", () => {
                const isOpen = dayList.style.display !== "none";
                if (isOpen) {
                    Anim.treeCollapse(dayList, () => {
                        dayList.style.display = "none";
                        monthLabel.textContent = `▶ ${monthNode.month}月`;
                    });
                } else {
                    dayList.style.display = "block";
                    Anim.treeExpand(dayList);
                    Anim.treeDaysEntrance(dayList);
                    monthLabel.textContent = `▼ ${monthNode.month}月`;
                }
            });

            monthGroup.appendChild(monthLabel);
            monthGroup.appendChild(dayList);
            monthsContainer.appendChild(monthGroup);
        });

        // 展开/折叠年份
        yearLabel.addEventListener("click", () => {
            const isOpen = monthsContainer.style.display !== "none";
            if (isOpen) {
                Anim.treeCollapse(monthsContainer, () => {
                    monthsContainer.style.display = "none";
                    yearLabel.textContent = `▶ ${yearNode.year}年`;
                });
            } else {
                monthsContainer.style.display = "block";
                Anim.treeExpand(monthsContainer);
                yearLabel.textContent = `▼ ${yearNode.year}年`;
            }
        });

        yearGroup.appendChild(yearLabel);
        yearGroup.appendChild(monthsContainer);
        dom.historyTree.appendChild(yearGroup);
    });

    // 历史树入场
    gsap.from(dom.historyTree.children, {
        x: -16,
        opacity: 0,
        stagger: 0.06,
        duration: 0.4,
        ease: "power3.out",
    });
}

async function loadDayRecord(date, dayElement) {
    // 高亮选中
    $$(".day-item.active").forEach((el) => el.classList.remove("active"));
    if (dayElement) {
        dayElement.classList.add("active");
        // 小弹跳反馈
        gsap.fromTo(dayElement, { scale: 1 }, { scale: 1.12, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out" });
    }

    try {
        const resp = await fetch(`${API_BASE}/records?date=${date}`);
        const data = await resp.json();

        if (!resp.ok) throw new Error(data.detail || "加载失败");

        state.currentDate = date;
        state.newsData = data;

        if (data.news && data.news.length > 0) {
            state.status = "LOADED";
            renderNewsList(data);

            // 隐藏其他状态
            dom.stateEmpty.style.display = "none";
            dom.stateLoading.style.display = "none";
            dom.stateError.style.display = "none";
            dom.stateLoaded.style.display = "block";

            dom.resultBadge.textContent = `📂 历史 · ${data.count} 条`;
            Anim.stateToLoaded(data);

        } else if (data.markdown) {
            dom.modalTitle.textContent = `📝 AI 新闻日报 — ${date}`;
            dom.modalBody.innerHTML = `<div class="markdown-body">${marked.parse(data.markdown)}</div>`;
            Anim.modalOpen();
        }

    } catch (err) {
        Anim.toast("加载失败: " + err.message, "error");
    }
}

// ═══════════════════════════════════════════════════
// 工具函数
// ═══════════════════════════════════════════════════
function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
