// background.js (service worker)
// 负责：创建右键菜单、处理右键点击（调用后端）、把结果保存到 chrome.storage 并启用/打开 sidePanel

// 1) 安装时创建右键菜单（仅在有文本选中时显示）
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "sendToReadNote",
    title: "发送到 ReadNote（生成笔记）",
    contexts: ["selection"]
  });

  // 可配置：当用户点击扩展图标时打开侧栏（无需 popup）
  // 如果希望点击工具栏按钮打开侧栏，设置此行为：
  chrome.sidePanel?.setPanelBehavior?.({ openPanelOnActionClick: true })
    .catch((e) => {
      // 某些早期/特定版本可能不支持，捕获异常以免 service worker 报错
      console.warn("setPanelBehavior not supported or failed:", e);
    });
});

// 监听来自后端的认证回调消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "MICROSOFT_AUTH_SUCCESS") {
    // 保存认证信息
    chrome.storage.local.set({
      authToken: request.token,
      userInfo: request.userInfo
    }).then(() => {
      console.log("认证信息已保存");
    });
  }
});

// 2) 右键菜单点击处理
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "sendToReadNote") return;
  if (!info.selectionText) return;

  // 检查用户是否已登录
  const { authToken } = await chrome.storage.local.get(["authToken"]);
  if (!authToken) {
    // 用户未登录，通知侧边栏显示登录提示
    const pending = {
      user: info.selectionText,
      source: info.pageUrl || (tab && tab.url) || "",
      status: "need_login",
      createdAt: Date.now()
    };

    const { conversations = [] } = await chrome.storage.local.get(["conversations"]);
    conversations.push(pending);
    await chrome.storage.local.set({ conversations });

    // 启用并打开侧边栏
    try {
      if (tab && tab.id != null) {
        await chrome.sidePanel.setOptions({
          tabId: tab.id,
          path: "sidepanel.html",
          enabled: true
        });
        await chrome.sidePanel.open().catch(e => console.warn("sidePanel.open() failed:", e));
      } else {
        await chrome.sidePanel.open().catch(e => console.warn("sidePanel.open() failed (no tab):", e));
      }
    } catch (e) {
      console.warn("setOptions/open error:", e);
    }

    return;
  }

  const selectedText = info.selectionText;
  const pageUrl = info.pageUrl || (tab && tab.url) || "";

  // 把用户选中和来源先写入 storage（方便 sidePanel 立即显示"发送中"状态）
  const pending = {
    user: selectedText,
    source: pageUrl,
    status: "sending",
    createdAt: Date.now()
  };

  // 把 pending 加到 conversations 中（简单队列）
  const { conversations = [] } = await chrome.storage.local.get(["conversations"]);
  conversations.push(pending);
  await chrome.storage.local.set({ conversations });

  // 选项：启用 sidePanel 在当前 tab（只在需要时）
  try {
    if (tab && tab.id != null) {
      await chrome.sidePanel.setOptions({
        tabId: tab.id,         // 该侧栏只在这个 tab 可用（可选）
        path: "sidepanel.html",// sidepanel 页面路径（必须在扩展内）
        enabled: true
      });
      // 可选：立即打开侧栏（用户也可以手动打开）
      // 注意：有时 open() 在某些版本会报错，故加 try/catch
      await chrome.sidePanel.open().catch(e => console.warn("sidePanel.open() failed:", e));
    } else {
      // 没有 tab 信息时可以用全局默认侧栏（manifest 中的 default_path 已设置）
      await chrome.sidePanel.open().catch(e => console.warn("sidePanel.open() failed (no tab):", e));
    }
  } catch (e) {
    console.warn("setOptions/open error:", e);
  }

  // 3) 调用后端生成笔记（示例：POST /api/note），并在完成后更新 storage
  try {
    const resp = await fetch("http://127.0.0.1:8000/api/note", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authToken}`
      },
      body: JSON.stringify({ text: selectedText, url: pageUrl })
    });

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
    }

    const json = await resp.json();

    // 更新刚刚的 pending 条目为 completed（简单做法：用数组末尾）
    const updated = (await chrome.storage.local.get(["conversations"])).conversations || [];
    // 找到 pending（粗略匹配）
    for (let i = updated.length - 1; i >= 0; i--) {
      if (updated[i].status === "sending" && updated[i].user === selectedText) {
        updated[i].status = "done";
        updated[i].ai = json.note || json; // 存后端返回的 note
        updated[i].completedAt = Date.now();
        break;
      }
    }
    await chrome.storage.local.set({ conversations: updated });
    // sidePanel 页面会监听 storage.onChanged 自动刷新
  } catch (err) {
    console.error("call backend failed:", err);
    // 更新为失败状态
    const updated = (await chrome.storage.local.get(["conversations"])).conversations || [];
    for (let i = updated.length - 1; i >= 0; i--) {
      if (updated[i].status === "sending" && updated[i].user === selectedText) {
        updated[i].status = "error";
        updated[i].error = (err && err.message) || String(err);
        updated[i].completedAt = Date.now();
        break;
      }
    }
    await chrome.storage.local.set({ conversations: updated });
  }
});
