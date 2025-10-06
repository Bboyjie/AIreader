

# 🧠 AIreader

> 一款以浏览器为入口的智能笔记管理工具，让你的知识真正“活”起来。

---

## ✨ 项目简介

**AIreader** 是一款基于浏览器的智能笔记管理工具，支持从网页直接捕获内容，并通过大语言模型（LLM）将其自动转化为结构化笔记，存储至 **Microsoft OneNote**。

无论是浏览文章、查阅文献，还是整理学习资料，AIreader 都能帮你一键记录、智能摘要、自动整合，实现从“阅读”到“掌握”的高效转化。

---

## 🚀 主要功能

* 🌐 **网页内容一键笔记化**
  自动将网页或选中内容整理为 OneNote 笔记。

* 🪄 **智能笔记摘要**
  基于大模型自动生成简洁摘要，快速提炼核心信息。

* 🧩 **追加与整合笔记**
  在不丢失原内容的前提下，智能合并新旧笔记。

* 📚 **基于笔记的复习与问答**
  自动生成个性化复习题，支持交互式学习与知识回顾。

* 🧠 **未来计划（开发中）**

  * 多源笔记同步
  * 知识图谱联动
  * 个性化学习建议
  * 多笔记自动分析与分类
  * 适配 Markdown 与其他笔记软件

> 💡 **愿景**：让浏览器成为你的知识中枢，让笔记不仅被记录，更能被理解与运用。

---

## ⚙️ 使用教程

### 1️⃣ 配置 Azure OneNote

1. 访问 [Azure Portal](https://portal.azure.com)
2. 搜索 **“应用注册”** 并新建一个应用。
3. 按以下步骤完成设置：

**认证设置：** <img width="1106" height="603" alt="auth" src="https://github.com/user-attachments/assets/f41bdfa5-f8a0-4070-a4ab-bded346cafeb" />

**创建 Secret：** <img width="1011" height="254" alt="secret" src="https://github.com/user-attachments/assets/1c3b8c59-2e71-4820-a9ba-f1a035fd0a37" />

**获取 Client ID：** <img width="592" height="422" alt="client id" src="https://github.com/user-attachments/assets/2465479f-8b83-481c-af00-d69ccd22b519" />

**添加权限：** <img width="570" height="456" alt="permissions" src="https://github.com/user-attachments/assets/281d1da8-ac60-4a17-85ea-f34c7735c8e9" />

---

### 2️⃣ 配置环境变量

填写backend文件夹下 `.env` 文件，填写以下内容：

```bash
ONENOTE_CLIENT_ID=Azure
ONENOTE_CLIENT_SECRET=Azure
ONENOTE_REDIRECT_URI=Azure
OPENAI_API_KEY=LLM api key
BASE_URL=LLM base url
MODEL=LLM 模型 例如qwen/qgt....
```

---

### 3️⃣ 启动后端服务

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8002
```

确保后台运行正常后，即可连接浏览器插件。

---

### 4️⃣ 安装 Chrome 插件

打开 Chrome 扩展管理页面，启用开发者模式，然后加载打包的插件文件夹。

**插件示例界面：** <img width="883" height="274" alt="plugin" src="https://github.com/user-attachments/assets/11004d8c-0844-4f94-8234-cd8a1098f38c" />

**未登录界面预览：** <img width="487" height="668" alt="login" src="https://github.com/user-attachments/assets/10b69b77-6688-47e8-ac43-52e62dd224a1" />

---

## 📝 功能演示

完成配置后，您可以：

* 创建分区与笔记页面
* 为当前笔记生成摘要
* 自动生成复习题（可指定题目数量）
* 执行复习分析与知识强化
* 追加新内容到现有笔记

---

## 🔮 待更新功能

* 📅 日程与任务管理
* 🧭 自动笔记整理与聚类
* 🧾 多笔记关联分析
* 🧱 支持 Markdown 与 Notion 等外部笔记格式

---

## 🤝 贡献指南

欢迎提交 Issue、PR 或提出新功能建议！
如果你有兴趣参与该项目开发，请联系维护者或直接提交 PR。

---

## 🧩 作者

**AIreader** 由个人开发，旨在探索大模型与知识管理结合的实际落地场景。
未来将持续完善智能学习、跨源笔记融合与个性化知识推荐功能。

---




## ⚠️ License and Usage Notice
This repository is distributed under the **CC BY-NC 4.0 License**.  
🚫 **Commercial use is strictly prohibited** without explicit written permission.

If you wish to use this project or its derivatives for commercial purposes, please contact:
- **Author**: Bboyjie  
- **Email**: [2501845673@qq.com]  

> Unauthorized commercial use (including integration into closed-source products, resale, or deployment for profit) will be considered copyright infringement.



