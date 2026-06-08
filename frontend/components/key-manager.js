/**
 * KeyBox — API Key 管理面板 v2
 * GSAP 动画增强 · 平滑交互
 */

// 内置 Provider fallback（后端不可用时兜底，与 backend/models/keybox.py 保持同步）
const FALLBACK_PROVIDERS = [
    { id: "openai", display_name: "OpenAI", models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini"], requires_org_id: true },
    { id: "anthropic", display_name: "Anthropic", models: ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"], requires_org_id: false },
    { id: "deepseek", display_name: "DeepSeek", models: ["deepseek-chat", "deepseek-reasoner"], requires_org_id: false },
    { id: "agnes-ai", display_name: "Agnes AI", models: ["agnes-pro", "agnes-fast"], requires_org_id: false },
    { id: "google", display_name: "Google AI", models: ["gemini-2.5-pro", "gemini-2.5-flash"], requires_org_id: false },
    { id: "zhipu", display_name: "智谱 GLM", models: ["glm-4-plus", "glm-4-flash", "glm-4-flashx"], requires_org_id: false },
    { id: "moonshot", display_name: "Moonshot (Kimi)", models: ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"], requires_org_id: false },
    { id: "qwen", display_name: "通义千问", models: ["qwen-max", "qwen-plus", "qwen-turbo"], requires_org_id: false },
];

const KeyManager = {
    providers: [],
    keys: [],

    async init() {
        document.getElementById("btnSettings").addEventListener("click", () => this.open());
        document.getElementById("btnKeyboxClose").addEventListener("click", () => this.close());

        const overlay = document.getElementById("keyboxOverlay");
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) this.close();
        });

        // ESC 关闭
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && overlay.style.display === "flex") {
                this.close();
            }
        });
    },

    // ── 打开/关闭 ──────────────────────────────────

    async open() {
        const overlay = document.getElementById("keyboxOverlay");
        const panel = document.getElementById("keyboxPanel");

        overlay.style.display = "flex";

        // 入场动画
        const tl = gsap.timeline();
        tl.fromTo(overlay, { opacity: 0 }, { opacity: 1, duration: 0.22 });
        tl.fromTo(panel,
            { scale: 0.85, opacity: 0, y: 24 },
            { scale: 1, opacity: 1, y: 0, duration: 0.45, ease: "elastic.out(1, 0.55)" },
            "-=0.12"
        );

        // 加载数据
        await Promise.all([this.loadProviders(), this.loadKeys()]);
        this.render();

        // 渲染后动画 — Key 列表 stagger 入场
        gsap.from(".key-item", {
            x: -20,
            opacity: 0,
            stagger: 0.06,
            duration: 0.35,
            ease: "power3.out",
        });
    },

    close() {
        const overlay = document.getElementById("keyboxOverlay");
        const panel = document.getElementById("keyboxPanel");

        const tl = gsap.timeline({
            onComplete: () => { overlay.style.display = "none"; },
        });

        tl.to(panel, { scale: 0.92, opacity: 0, y: 12, duration: 0.2, ease: "power2.in" });
        tl.to(overlay, { opacity: 0, duration: 0.18 }, "-=0.1");
    },

    // ── 数据加载 ────────────────────────────────────

    async loadProviders() {
        try {
            const resp = await fetch(`${API_BASE}/keys/providers`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            this.providers = data.length > 0 ? data : FALLBACK_PROVIDERS;
        } catch (e) {
            console.warn("加载 Provider 失败，使用内置列表:", e.message);
            this.providers = FALLBACK_PROVIDERS;
        }
    },

    async loadKeys() {
        try {
            const resp = await fetch(`${API_BASE}/keys`);
            this.keys = await resp.json();

            // 更新顶栏
            const enabled = this.keys.filter(k => k.is_enabled);
            const llmLabel = document.getElementById("currentLLM");
            if (enabled.length > 0) {
                llmLabel.textContent = enabled[0].provider_name || enabled[0].provider_id;
            } else {
                llmLabel.textContent = "未配置";
            }
        } catch (e) {
            console.error("加载 Keys 失败:", e);
            this.keys = [];
        }
    },

    // ── 渲染 ────────────────────────────────────────

    render() {
        const body = document.getElementById("keyboxBody");

        // 已保存的 Keys
        const savedKeysHtml = this.keys.length === 0
            ? '<p style="color:#6b7280;font-size:0.85rem;text-align:center;padding:24px;">暂无已保存的 Key<br><span style="font-size:0.75rem;">在下方添加你的第一个 API Key</span></p>'
            : this.keys.map(k => `
                <div class="key-item" data-key-id="${k.id}">
                    <div class="key-item-left">
                        <span class="key-dot ${k.is_enabled ? 'active' : 'inactive'}"></span>
                        <span><strong>${escapeHtml(k.provider_name || k.provider_id)}</strong></span>
                        ${k.label ? `<span style="color:#6b7280;">· ${escapeHtml(k.label)}</span>` : ""}
                        <code style="font-size:0.7rem;color:#9ca3af;">${k.masked_key}</code>
                        <span style="font-size:0.7rem;color:#9ca3af;">${k.usage_count} 次</span>
                    </div>
                    <div class="key-item-right">
                        <button class="btn-sm" onclick="KeyManager.testKey(${k.id}, this)">
                            🧪 测试
                        </button>
                        <button class="btn-sm danger" onclick="KeyManager.deleteKey(${k.id}, this)">
                            🗑
                        </button>
                    </div>
                </div>
            `).join("");

        // Provider 选项
        const providerOptions = this.providers.map(p =>
            `<option value="${p.id}">${p.display_name} — ${(p.models || []).slice(0, 2).join(", ")}</option>`
        ).join("");

        body.innerHTML = `
            <div class="keybox-section">
                <h4>🔑 已保存的 Keys</h4>
                <div id="savedKeysContainer">${savedKeysHtml}</div>
            </div>

            <div class="keybox-section">
                <h4>➕ 添加新 Key</h4>
                <div class="key-form" id="addKeyForm">
                    <label>提供商</label>
                    <select id="keyboxProvider">${providerOptions}</select>

                    <label>标签（可选）</label>
                    <input type="text" id="keyboxLabel" placeholder="例如：工作账号">

                    <label>API Key <span style="color:#ef4444;">*</span></label>
                    <input type="password" id="keyboxKey" placeholder="sk-...">
                    <span style="font-size:0.68rem;color:#9ca3af;">🔒 加密存储，不会明文传输</span>

                    <label id="orgIdLabel" style="display:none;">Org ID</label>
                    <input type="text" id="keyboxOrgId" placeholder="org-..." style="display:none;">

                    <button class="btn-primary-sm" id="btnSaveKey">💾 保存 Key</button>
                </div>
            </div>
        `;

        // 绑定事件
        document.getElementById("btnSaveKey").addEventListener("click", () => this.addKey());

        const provSelect = document.getElementById("keyboxProvider");
        const orgLabel = document.getElementById("orgIdLabel");
        const orgInput = document.getElementById("keyboxOrgId");

        provSelect.addEventListener("change", () => {
            const prov = this.providers.find(p => p.id === provSelect.value);
            const show = prov && prov.requires_org_id;
            orgLabel.style.display = show ? "block" : "none";
            orgInput.style.display = show ? "block" : "none";

            if (show) {
                gsap.fromTo([orgLabel, orgInput], { opacity: 0, y: -6 }, { opacity: 1, y: 0, duration: 0.25, stagger: 0.05 });
            }
        });
        provSelect.dispatchEvent(new Event("change"));

        // 表单入场动画
        gsap.from("#addKeyForm", { y: 16, opacity: 0, duration: 0.4, ease: "power3.out" });
    },

    // ── CRUD 操作 ──────────────────────────────────

    async addKey() {
        const providerId = document.getElementById("keyboxProvider").value;
        const label = document.getElementById("keyboxLabel").value.trim();
        const apiKey = document.getElementById("keyboxKey").value.trim();
        const orgId = document.getElementById("keyboxOrgId").value.trim();
        const btnSave = document.getElementById("btnSaveKey");

        if (!apiKey) {
            Anim.toast("请输入 API Key", "error");
            this._shakeElement(document.getElementById("keyboxKey"));
            return;
        }

        // 按钮加载态
        btnSave.disabled = true;
        btnSave.textContent = "⏳ 保存中...";
        gsap.to(btnSave, { scale: 0.95, duration: 0.15 });

        try {
            const resp = await fetch(`${API_BASE}/keys`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ provider_id: providerId, label, api_key: apiKey, org_id: orgId }),
            });

            const data = await resp.json();

            if (!resp.ok) throw new Error(data.detail || "保存失败");

            // 成功反馈
            Anim.toast(`Key 已加密保存 (${data.masked_key})`, "success");

            // 清空表单
            document.getElementById("keyboxKey").value = "";
            document.getElementById("keyboxLabel").value = "";
            document.getElementById("keyboxOrgId").value = "";

            // 刷新列表
            await this.loadKeys();
            this.render();

            // 新 Key 高亮
            const newItem = document.querySelector(`[data-key-id="${data.id}"]`);
            if (newItem) {
                gsap.fromTo(newItem,
                    { backgroundColor: "#f0fdf4" },
                    { backgroundColor: "#ffffff", duration: 0.8, ease: "power2.out" }
                );
            }

        } catch (e) {
            Anim.toast(e.message, "error");
        } finally {
            btnSave.disabled = false;
            btnSave.textContent = "💾 保存 Key";
            gsap.to(btnSave, { scale: 1, duration: 0.25, ease: "elastic.out(1, 0.5)" });
        }
    },

    async testKey(keyId, btnEl) {
        // 按钮加载态
        const origText = btnEl.textContent;
        btnEl.textContent = "⏳";
        btnEl.disabled = true;

        try {
            const resp = await fetch(`${API_BASE}/keys/${keyId}/test`, { method: "POST" });
            const data = await resp.json();

            if (data.valid) {
                Anim.toast("Key 有效！" + (data.message || ""), "success");
                // 小弹跳
                gsap.fromTo(btnEl, { scale: 1 }, { scale: 1.25, duration: 0.15, yoyo: true, repeat: 1, ease: "power2.out" });
            } else if (data.valid === null) {
                Anim.toast(data.message, "info");
            } else {
                Anim.toast("Key 无效: " + (data.message || "未知错误"), "error");
                this._shakeElement(btnEl);
            }
        } catch (e) {
            Anim.toast("测试请求失败: " + e.message, "error");
        } finally {
            btnEl.textContent = origText;
            btnEl.disabled = false;
        }
    },

    async deleteKey(keyId, btnEl) {
        // 确认删除
        const keyItem = btnEl.closest(".key-item");
        if (!confirm("确定要删除这个 Key 吗？此操作不可撤销。")) return;

        try {
            // 删除动画
            if (keyItem) {
                await gsap.to(keyItem, {
                    x: 40,
                    opacity: 0,
                    scale: 0.9,
                    duration: 0.3,
                    ease: "power2.in",
                });
            }

            const resp = await fetch(`${API_BASE}/keys/${keyId}`, { method: "DELETE" });

            if (resp.ok) {
                await this.loadKeys();
                this.render();
                Anim.toast("Key 已删除", "info");

                // 重新 stagger 入场
                gsap.from(".key-item", {
                    x: -20,
                    opacity: 0,
                    stagger: 0.06,
                    duration: 0.35,
                    ease: "power3.out",
                });
            } else {
                const data = await resp.json();
                Anim.toast("删除失败: " + (data.detail || "未知错误"), "error");

                // 恢复
                if (keyItem) {
                    gsap.to(keyItem, { x: 0, opacity: 1, scale: 1, duration: 0.3, ease: "power2.out" });
                }
            }
        } catch (e) {
            Anim.toast("删除失败: " + e.message, "error");
            if (keyItem) {
                gsap.to(keyItem, { x: 0, opacity: 1, scale: 1, duration: 0.3, ease: "power2.out" });
            }
        }
    },

    // ── 微交互 ──────────────────────────────────────

    /** 摇动动画（错误反馈） */
    _shakeElement(el) {
        gsap.to(el, {
            x: [-6, 6, -5, 5, -3, 3, 0],
            duration: 0.5,
            ease: "power2.out",
        });
    },
};

// 页面加载时自动初始化
document.addEventListener("DOMContentLoaded", () => KeyManager.init());
