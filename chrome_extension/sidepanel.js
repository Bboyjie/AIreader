
let darkMode = false;
let isLoggedIn = false;
let originalSendFunction = null;
const chatContainer = document.getElementById("chat-container");
const notebookSelect = document.getElementById("notebook-select");
const sectionSelect = document.getElementById("section-select");
const pageSelect = document.getElementById("page-select");
const newPageBtn = document.getElementById("new-page-btn");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const userInfo = document.getElementById("user-info");
const loginBtn = document.getElementById("login-btn");
const logoutBtn = document.getElementById("logout-btn");
const notebookSection = document.getElementById("notebook-section");
showUserInfo();

// 切换主题
document.getElementById("toggle-theme").addEventListener("click", () => {
  darkMode = !darkMode;
  document.body.className = darkMode ? "dark-mode" : "";
});

// 更新已登录用户的UI
function updateUIForLoggedInUser(user) {
  isLoggedIn = true;
  userInfo.textContent = `欢迎, ${user.displayName || user.displayName || '用户'}`;
  loginBtn.style.display = "none";
  logoutBtn.style.display = "block";
  notebookSection.style.display = "flex";
  userInput.disabled = false;
  sendBtn.disabled = false;

  // 加载笔记数据
  loadNotebooks();
  // renderHistory();
}

// 更新未登录用户的UI
function updateUIForLoggedOutUser() {
  isLoggedIn = false;
  userInfo.textContent = "未登录";
  loginBtn.style.display = "block";
  logoutBtn.style.display = "none";
  notebookSection.style.display = "none";
  userInput.disabled = true;
  sendBtn.disabled = true;
}

// 修改登录按钮事件监听器
loginBtn.addEventListener("click", async () => {
 try {
    // 1. 请求后端获取登录 URL（含 CSRF state）
    const res = await fetch('http://localhost:8002/login', {
      credentials: 'include' // 重要：携带 cookie
    });
    const { login_url } = await res.json();
    // 2. 打开授权页面（推荐新窗口，避免 popup 被拦截）
    const authWindow = window.open(login_url, 'oauth', 'width=600,height=700');

    // 3. 监听来自 /auth/success 的消息
    const handleMessage = (event) => {
      if (event.origin !== 'http://localhost:8002') return;
      if (event.data.type === 'oauth_success') {
        authWindow.close();
        window.removeEventListener('message', handleMessage);
        showUserInfo(); // 加载用户信息
      } else if (event.data.type === 'oauth_error') {
        authWindow.close();
        alert('登录失败: ' + event.data.message);
      }
    };

    window.addEventListener('message', handleMessage);
  } catch (err) {
    alert('启动登录失败: ' + err.message);
  }
});

async function showUserInfo() {
  const res = await fetch('http://localhost:8002/profile', {
    credentials: 'include'
  });
  if (res.ok) {
    const { user } = await res.json();
    updateUIForLoggedInUser(user);
  } else {
    // 未登录，显示登录按钮
    document.getElementById('login-section').style.display = 'block';
  }
}

// 渲染聊天气泡
function addChatBubble(userText, aiText) {
  if (userText) {
    const userDiv = document.createElement("div");
    userDiv.className = "chat-bubble user-bubble";
    userDiv.textContent = userText;
    chatContainer.appendChild(userDiv);
  }
  if (aiText) {
    const aiDiv = document.createElement("div");
    aiDiv.className = "chat-bubble ai-bubble";
    aiDiv.textContent = aiText;
    chatContainer.appendChild(aiDiv);
  }
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 加载历史对话
function renderHistory() {
  chrome.storage.local.get({ conversations: [] }, (res) => {
    chatContainer.innerHTML = "";
    res.conversations.forEach(conv => addChatBubble(conv.user, conv.replay));
  });
}

// 发送按钮逻辑
// sendBtn.addEventListener("click",)
async function defaultSendFunction() {
  const text = userInput.value.trim();
  if (!text) return;
  addChatBubble(text, null);
  addChatBubble(null, "正在思考...");
  userInput.value = "";
  // 获取认证token
  // 默认使用当前选中分区和页面
  const pageId = pageSelect.value;
  const res = await fetch("http://localhost:8002/api/dialogue", {
    credentials: 'include',  // ← 自动携带 auth_session cookie
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_print: text,
      page_id: pageId,
    })
  });

  if (!res.ok) {
    if (res.status === 401) {
      // Token过期或无效，清除存储并提示重新登录
      await chrome.storage.local.remove(["authToken", "userInfo"]);
      isLoggedIn = false;
      userInfo.textContent = "未登录";
      loginBtn.style.display = "block";
      logoutBtn.style.display = "none";
      notebookSection.style.display = "none";
      userInput.disabled = true;
      sendBtn.disabled = true;
      alert("登录已过期，请重新登录");
      return;
    }
    const errorData = await res.json();
    alert(`请求失败: ${errorData.message || '未知错误'}`);
    return;
  }

  let data;
  try {
    data = await res.json();
  } catch(e) {
    console.error("后端返回非 JSON:", await res.text());
    return;
  }
  addChatBubble(null, data.replay);
  // 保存到本地存储并渲染
    chrome.storage.local.get({ conversations: [] }, (result) => {
    const conv = result.conversations;
    conv.push({ user: text, replay: data.replay });
    chrome.storage.local.set({ conversations: conv });
    // 只渲染新消息
  });
}
originalSendFunction = defaultSendFunction;

sendBtn.onclick = defaultSendFunction;

// 初始化加载笔记本/分区/页面
async function loadNotebooks() {
   try {
    const res = await fetch("http://localhost:8002/api/notebooks", {
      credentials: 'include'  // ← 自动携带 auth_session cookie
    });
    if (res.ok) {
      const notebooks = await res.json();
      notebookSelect.innerHTML = "";
      notebooks.forEach(nb => notebookSelect.add(new Option(nb.displayName, nb.id)));
      if (notebooks.length > 0) loadSections(notebooks[0].id);
      // 处理数据
    } else if (res.status === 401) {
      // 未登录，跳转登录
      alert("请先登录");
    }
  } catch (err) {
    console.error("加载笔记本失败:", err);
  }
}

async function loadSections(notebookId) {
  try {
    const res = await fetch(`http://localhost:8002/api/sections/${notebookId}`, {
      credentials: 'include'  // ← 自动携带 auth_session cookie
    });
     if (res.ok) {
        const sections = await res.json();
        sectionSelect.innerHTML = "";
        sections.forEach(sec => sectionSelect.add(new Option(sec.displayName, sec.id)));
        if (sections.length > 0) loadPages(sections[0].id);
      // 处理数据
    } else if (res.status === 401) {
      // 未登录，跳转登录
        alert("登录已过期，请重新登录");
    }
  } catch (err) {
    console.error("加载分区失败:", err);
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);

  }
}

async function loadPages(sectionId) {
  try {
    const res = await fetch(`http://localhost:8002/api/pages/${sectionId}`, {
      credentials: 'include'  // ← 自动携带 auth_session cookie
    });
     if (res.ok) {
      const pages = await res.json();
      pageSelect.innerHTML = "";
      pages.forEach(pg => pageSelect.add(new Option(pg.title, pg.id)));
      // 处理数据
    } else if (res.status === 401) {
      // 未登录，跳转登录
        alert("登录已过期，请重新登录");
    }
  } catch (err) {
    console.error("加载页面失败:", err);
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);

  }
}

// 监听选择变化
notebookSelect.addEventListener("change", e => loadSections(e.target.value));
sectionSelect.addEventListener("change", e => loadPages(e.target.value));


// 新建页面
document.getElementById("new-page-btn").addEventListener("click", async () => {
   if (!isLoggedIn) {
      alert("请先登录");
      return;
    }
  addChatBubble(null, "请输入页面标题:");
  const pageTitle = await new Promise((resolve) => {
    // 定义临时的发送按钮处理函数
    sendBtn.onclick = () => {
      const title = userInput.value.trim();
      if (!title) {
        addChatBubble(null, "标题不能为空，请重新输入:");
        return;
      }
      // 输入有效，显示用户输入的标题
      addChatBubble(title, null);
      // 解析 Promise，传递用户输入的标题
      resolve(title);
    };
  });
  addChatBubble(null, "请输入页面内容:");
  userInput.placeholder = "请输入页面内容...";
  userInput.value = "";
  const pageContent = await new Promise((resolve) => {
    // 定义临时的发送按钮处理函数
    sendBtn.onclick = () => {
      const content = userInput.value.trim();
      if (!content) {
        addChatBubble(null, "内容不能为空，请重新输入:");
        return;
      }
      // 输入有效，显示用户输入的内容
      // 解析 Promise，传递用户输入的内容
      resolve(content);
    };
  });
  addChatBubble(pageContent, null);
    sendBtn.onclick =originalSendFunction
    userInput.placeholder = "请输入对话...";
    userInput.value = "";
    userInput.focus();
  // 弹窗要求输入标题和内容
  if (!pageTitle) return;
  if (!pageContent) return;
  const sectionId = sectionSelect.value;
  if (!sectionId) {
    alert("请先选择一个分区");
    return;
  }
  try {
    // 调用后端API创建新页面
    const res = await fetch("http://localhost:8002/api/create-page", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: 'include',
      body: JSON.stringify({
        section_id: sectionId,
        title: pageTitle,
        content: pageContent
      })
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();

    // 更新页面选择信息
    await loadPages(sectionId);

    // 在聊天界面显示成功消息
    const pageDiv = document.createElement("div");
    pageDiv.className = "bubble ai";
    pageDiv.innerHTML = `      <div class="note-title">📄 页面创建成功</div>
      <div class="note-summary">已成功创建页面: ${pageTitle}</div>
      <div class="note-summary">页面ID: ${data.id}</div>
    `;
    chatContainer.appendChild(pageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  } catch (err) {
    console.error("创建页面失败:", err);
    alert("创建页面失败: " + err.message);
  }
});
// 摘要
document.getElementById("note-summary").addEventListener("click", async () => {
  if (!isLoggedIn) {
    alert("请先登录");
    return;
  }
  try {
    // 获取当前选中的页面ID
    const pageId = pageSelect.value;
    if (!pageId) {
      alert("请先选择一个页面");
      return;
    }
    addChatBubble(null, "正在基于当前笔记生成摘要...."); // 显示用户输入的内容

    // 调用后端API生成当前页面的摘要
    const res = await fetch("http://localhost:8002/api/page-summary", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: 'include',
      body: JSON.stringify({
        page_id: pageId
      })
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();

    // 显示在聊天界面
    const summaryDiv = document.createElement("div");
    const safeSummaryHTML =data.pagesummary;

    summaryDiv.innerHTML = `
      <div class="note-title">📝 页面摘要</div>
      <div class="note-summary">${safeSummaryHTML}</div>
    `;
    chatContainer.appendChild(summaryDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

  } catch (err) {
    console.error("生成页面摘要失败:", err);
    alert("生成页面摘要失败: " + err.message);
  }
});
// 复习
document.getElementById("review-notes").addEventListener("click", async () => {
  if (!isLoggedIn) {
    alert("请先登录");
    return;
  }
  addChatBubble(null, "请输入题目个数");

  const question_num = await new Promise((resolve) => {
    // 定义临时的发送按钮处理函数
    sendBtn.onclick = () => {
      const val = userInput.value.trim();
      if (!val || isNaN(val) || parseInt(val) <= 0) {
        addChatBubble(null, "请输入有效的正整数！");
        return;
      }

      // 输入有效，显示用户输入的数字

      // 恢复原始发送按钮功能
      sendBtn.onclick = originalSendFunction;
      // 解析 Promise，传递用户输入的题目数量
      resolve(parseInt(val));
    };
  });
    addChatBubble(question_num, null);
    userInput.value = "";


  // TODO: 在这里调用你的大模型接口，生成题目
  // await fetchQuestions(question_num);

  // 移除这个临时监听器，避免重复触发

  try {
    // 获取当前选中的页面ID
    const pageId = pageSelect.value;
    if (!pageId) {
      alert("请先选择一个页面");
      return;
    }
    // 调用后端API生成当前页面的复习题目
    const res = await fetch("http://localhost:8002/api/review-questions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: 'include',
      body: JSON.stringify({
        page_id: pageId,
        question_num: question_num  // 生成5道题目
      })
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    if (typeof data.questions === 'string') {
      // 如果是字符串，则尝试解析JSON
      questions = JSON.parse(data.questions);
    } else {
      // 如果已经是对象，则直接使用
      questions = data.questions;
    }
    // 存储用户答案和题目
    const userAnswers = [];
    let currentQuestionIndex = 0;
    const totalQuestions = questions.length;

    // 显示第一题
    showQuestion(questions, currentQuestionIndex, userAnswers,totalQuestions);

  } catch (err) {
    console.error("生成复习内容失败:", err);
    alert("生成复习内容失败: " + err.message);
  }
});
// 显示题目函数
function showQuestion(questions, index, userAnswers,totalQuestions) {
  // if (index >= questions.length) {
  //   // 所有题目完成，提交答案到后端分析
  //   submitAnswersForAnalysis(userAnswers);
  //   return;
  // }

  const question = questions[index];
  // 显示题目
  const questionDiv = document.createElement("div");
  questionDiv.className = "bubble ai";
  questionDiv.innerHTML = `
    <div class="note-title">📚 复习时间 (第 ${index + 1} 题/共 ${questions.length} 题)</div>
    <div class="note-summary"><strong>题目:</strong> ${question.question}</div>
  `;

  chatContainer.appendChild(questionDiv);
  chatContainer.scrollTop = chatContainer.scrollHeight;

  // 设置输入框提示和清空内容
  userInput.placeholder = "请输入答案...";
  userInput.value = "";
  userInput.focus();

  // 修改发送按钮功能为提交答案
  sendBtn.onclick = () => {
    const userAnswer = userInput.value.trim();
    if (!userAnswer) {
      alert("请输入答案");
      return;
    }
    // 保存用户答案
    userAnswers.push({
      question: question.question,
      user_answer: userAnswer,
      correct_answer: question.answer,
      explanation: question.explanation
    });

  const answerDiv = document.createElement("div");
  answerDiv.className = "bubble ai";
  answerDiv.innerHTML = `
    <div class="note-title">📝 答案解析</div>
    <div class="note-summary"><strong>你的答案:</strong> ${userAnswer}</div>
    <div class="note-summary"><strong>标准答案:</strong> ${question.answer}</div>
    <div class="note-summary"><strong>解析:</strong> ${question.explanation}</div>
  `;

  chatContainer.appendChild(answerDiv);
  chatContainer.scrollTop = chatContainer.scrollHeight;

  // 如果还有题目，显示提示信息并准备下一题
  if (index < totalQuestions - 1) {
    const nextDiv = document.createElement("div");
    nextDiv.className = "bubble ai";
    nextDiv.innerHTML = `<div class="note-summary">请点击查看"下一题"按钮继续</div>`;
    chatContainer.appendChild(nextDiv);

    // 设置输入框提示
    userInput.placeholder = "点击按钮继续下一题";
    userInput.value = "";

    // 修改发送按钮为下一题按钮功能
    sendBtn.textContent = "下一题";
    sendBtn.onclick = () => {
      sendBtn.textContent = "发送";
       showQuestion(questions, index + 1, userAnswers,totalQuestions);
    }
  } else{
    // 所有题目完成
    const finishDiv = document.createElement("div");
    finishDiv.className = "bubble ai";
    finishDiv.innerHTML = `<div class="note-summary">✅ 所有题目已完成！正在分析你的学习情况...</div>`;
    chatContainer.appendChild(finishDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    try {
          sendBtn.onclick = originalSendFunction
         userInput.placeholder = "请输入对话...";
        userInput.value = "";
        userInput.focus();
        submitAnswersForAnalysis(userAnswers);
      } catch (error) {
          alert("调用 submitAnswersForAnalysis 函数时出错: " + error.message);
      }
    }
  };
}
async function submitAnswersForAnalysis(userAnswers) {
  try {
    const pageId = pageSelect.value;
    if (!pageId) {
      alert("请先选择一个页面");
      return;
    }
    const res = await fetch("http://localhost:8002/api/analyze-answers", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: 'include',
      body: JSON.stringify({
        question_a_answer: JSON.stringify(userAnswers),
        page_id: pageId,
      })
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    // 显示分析结果
    const analysisDiv = document.createElement("div");
    analysisDiv.className = "bubble ai";
    analysisDiv.innerHTML = `
      <div class="note-title">📊 学习分析报告</div>
      <div class="note-summary">${data.overall_suggestions}</div>
    `;
    chatContainer.appendChild(analysisDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // 恢复输入框和发送按钮的默认状态
    userInput.placeholder = "输入对话...";
    userInput.value = "";
    sendBtn.textContent = "发送";

  } catch (err) {
    console.error("分析答案失败:", err);
    alert("分析答案失败: " + err.message);
  }
}

// 添加新建分区功能
document.getElementById("new-section-btn").addEventListener("click", async () => {
  if (!isLoggedIn) {
    alert("请先登录");
    return;
  }


  const notebookId = notebookSelect.value;
  if (!notebookId) {
    alert("请先选择一个笔记本");
    return;
  }
    addChatBubble(null, "请输入分区名称！");

  const sectionName = await new Promise((resolve) => {
    // 定义临时的发送按钮处理函数
    sendBtn.onclick = () => {
      const section_Name = userInput.value.trim();
      if (!section_Name) {
        addChatBubble(null, "内容不能为空，请重新输入:");
        return;
      }
      // 输入有效，显示用户输入的内容
      // 解析 Promise，传递用户输入的内容
      resolve(section_Name);
    };
  });
  addChatBubble(sectionName, null);
    sendBtn.onclick =originalSendFunction
    userInput.placeholder = "请输入对话...";
    userInput.value = "";
    userInput.focus();
  try {
    // 调用后端创建新分区
    const res = await fetch(`http://localhost:8002/api/create-section`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: 'include',
      body: JSON.stringify({
        displayName: sectionName,
         notebook_id:notebookId

      })
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    // 重新加载分区列表
    await loadSections(notebookId);

    // 提示用户
    const successDiv = document.createElement("div");
    successDiv.className = "bubble ai";
    successDiv.innerHTML = `
      <div class="note-title">✅ 操作成功</div>
      <div class="note-summary">已成功创建新分区: ${sectionName}</div>
    `;
    chatContainer.appendChild(successDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

  } catch (err) {
    console.error("创建分区失败:", err);
    alert("创建分区失败: " + err.message);
  }
});

// 添加追加笔记功能
document.getElementById("append-notes").addEventListener("click", async () => {
if (!isLoggedIn) {
      alert("请先登录");
      return;
    }
  addChatBubble(null, "请输入页面内容：");

  userInput.placeholder = "请输入页面内容...";
  const pageContent = await new Promise((resolve) => {
    // 定义临时的发送按钮处理函数
    sendBtn.onclick = () => {
      const content = userInput.value.trim();
      if (!content) {
        addChatBubble(null, "内容不能为空，请重新输入:");
        return;
      }
      // 输入有效，显示用户输入的内容
      // 解析 Promise，传递用户输入的内容
      resolve(content);
    };
  });
  addChatBubble(pageContent, null);
  sendBtn.onclick =originalSendFunction
  userInput.placeholder = "请输入对话...";
  userInput.value = "";
  userInput.focus();
  // 弹窗要求输入标题和内容
  if (!pageContent) return;
  const pageId = pageSelect.value;
  const pagetitle = pageSelect.title;
  if (!pageId) {
    alert("请先选择一个分区");
    return;
  }
  try {
    // 调用后端API创建新页面
    const res = await fetch("http://localhost:8002/api/append-page", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: 'include',
      body: JSON.stringify({
        page_id: pageId,
        pageContent: pageContent
      })
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    // const data = await res.json();
    // 在聊天界面显示成功消息
    const pageDiv = document.createElement("div");
    pageDiv.className = "bubble ai";
    pageDiv.innerHTML = `      <div class="note-title">📄 追加笔记成功</div>
      <div class="note-summary">已成功追加到笔记: ${pagetitle}</div>
    `;
    chatContainer.appendChild(pageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  } catch (err) {
    console.error("追加失败:", err);
    alert("追加失败: " + err.message);
  }
});