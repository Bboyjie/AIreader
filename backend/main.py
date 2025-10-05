import json
import secrets
import traceback
from urllib.parse import urlencode
from fastapi import FastAPI, HTTPException, Request, status,Response
from fastapi.responses import RedirectResponse,HTMLResponse

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Any
import os
import requests
from dotenv import load_dotenv
from ulits import clean_onenote_content, llm_generate, extract_full_html, llm_json_parse
import logging
class AnalyzeAnswersResponse(BaseModel):
    overall_suggestions: str
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 确保输出到控制台
        logging.FileHandler('app.log')  # 同时输出到文件
    ]
)
# 允许 Chrome Extension 调用

# 加载环境变量
load_dotenv()
ONENOTE_CLIENT_ID = os.getenv("ONENOTE_CLIENT_ID")  # 可通过 OAuth2 获取
ONENOTE_CLIENT_SECRET = os.getenv("ONENOTE_CLIENT_SECRET")  # 可通过 OAuth2 获取
ONENOTE_REDIRECT_URI = os.getenv("ONENOTE_REDIRECT_URI")  # 可通过 OAuth2 获取


SCOPE = [
    "https://graph.microsoft.com/Notes.ReadWrite",
    "https://graph.microsoft.com/User.Read",
    "offline_access"
]
TOKEN_URL = r"https://login.microsoftonline.com/common/oauth2/v2.0/token"
AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
# 初始化 OpenAI 客户端（推荐使用新版 SDK）

app = FastAPI(title="ReadNote OneNote Backend")
# ⚠️ 安全提示：生产环境应限制 origins，不要用 ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8002",
        "http://127.0.0.1:8002",
        "chrome-extension://你的扩展ID"  # 例如：chrome-extension://abc123def456
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模拟用户 token 存储（生产环境应使用数据库 + session）
user_sessions = {}  # { session_id: { "access_token": "...", "refresh_token": "...", "user": "..." } }


# ----------------------------
# 模型定义
# ----------------------------
class NoteRequest(BaseModel):
    text: str
    notebook_id: Optional[str] = None
    section_id: Optional[str] = None
    page_id: Optional[str] = None
    create_new: bool = True


class NoteResponse(BaseModel):
    note: str
    page_url: Optional[str] = None


class OneNoteItem(BaseModel):
    id: str
    displayName: str

class OneNotePage(BaseModel):
    id: str
    title: str
    contentUrl: str
    lastModifiedDateTime: str
    createdByAppId: Optional[str] = None


# 替换现有的 CreatePageRequest 模型
class CreatePageRequest(BaseModel):
    section_id: str
    title: str
    content: str

    class Config:
        extra = "allow"  # 允许额外字段

class CreateSectionRequest(BaseModel):
    displayName: str
    notebook_id: str

    class Config:
        extra = "allow"  # 允许额外字段
class dialogueRequest(BaseModel):
    user_print: str
    page_id: str

    class Config:
        extra = "allow"  # 允许额外字段
    # 注意：没有 displayName
# ========== 临时存储（仅用于演示！）==========
# 生产环境请使用数据库、Redis 或加密 cookie

# ========== 工具函数 ==========
def get_session_id(request: Request) -> str:
    """从 cookie 获取或创建 session_id"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = secrets.token_urlsafe(32)
    return session_id

# ----------------------------
# 工具函数
# ----------------------------




def sync_to_onenote(
    token: str,
    note_text: str,
    section_id: Optional[str] = None,
    page_id: Optional[str] = None,
    create_new: bool = True
    ) -> str:
    """同步笔记到 OneNote"""
    if create_new:
        if not section_id:
            endpoint = "https://graph.microsoft.com/v1.0/me/onenote/pages"
        else:
            endpoint = f"https://graph.microsoft.com/v1.0/me/onenote/sections/{section_id}/pages"

        body = {
            "title": "AI 生成笔记",
            "content": f"<p>{note_text}</p>"
        }
        resp = onenote_request("POST", endpoint, token, body)
    else:
        if not page_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="page_id is required when create_new=False"
            )
        endpoint = f"https://graph.microsoft.com/v1.0/me/onenote/pages/{page_id}/content"
        body = [{
            "target": "body",
            "action": "append",
            "content": f"<p>{note_text}</p>"
        }]
        resp = onenote_request("PATCH", endpoint, token, body)

    return resp.get("links", {}).get("oneNoteWebUrl", {}).get("href")



def onenote_request(method: str, url: str, token: str, json_data: Optional[Any] = None) -> dict:
    """统一处理 OneNote API 请求"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        if method.upper() == "GET":
            r = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == "POST":
            r = requests.post(url, headers=headers, json=json_data, timeout=10)
        elif method.upper() == "PATCH":
            r = requests.patch(url, headers=headers, json=json_data, timeout=10)
        else:
            raise ValueError("Unsupported HTTP method")
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OneNote API request failed: {str(e)}"
        )

    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return r.json()



# ----------------------------
# API 路由
# ----------------------------


@app.get("/")
def read_root():
    return {"Hello": "World"}


# 模拟：用内存存储 user -> token 映射（生产环境用 DB）
user_info_store: dict[str, dict] = {}  # token -> user_info





@app.get("/login")
def login(request: Request):
    """生成授权 URL 并重定向用户到 Microsoft 登录页"""
    session_id = get_session_id(request)
    state = secrets.token_urlsafe(16)  # 用于防 CSRF
    # 临时保存 state（可存 DB，这里用 session_id 关联）
    user_sessions[session_id] = {"oauth_state": state}
    redirect_uri = f"{ONENOTE_REDIRECT_URI}?session_id={session_id}"

    params = {
        "client_id": ONENOTE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPE),
        "response_mode": "query",
        "state":state
    }

    auth_url = AUTH_URL + urlencode(params)
    return {"login_url": auth_url}



@app.get("/callback")
def callback(response: Response,request: Request):
    """接收授权码，换取 access_token，并保存到会话"""
    session_id = request.query_params.get("session_id")
    if not session_id or session_id not in user_sessions:
        raise HTTPException(status_code=400, detail="Invalid session")

    # 验证 state 防 CSRF
    expected_state = user_sessions[session_id].get("oauth_state")
    received_state = request.query_params.get("state")
    if received_state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")
    redirect_uri = f"{ONENOTE_REDIRECT_URI}?session_id={session_id}"

    # 换取 token
    data = {
        "client_id": ONENOTE_CLIENT_ID,
        "scope": " ".join(SCOPE),
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "client_secret": ONENOTE_CLIENT_SECRET,
    }
    try:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        r = requests.post(TOKEN_URL, headers=headers, data=data)
        r.raise_for_status()
        token_data = r.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")
    permanent_session_id = secrets.token_urlsafe(32)

    # 存储正式会话（可替换临时 session）
    user_sessions[permanent_session_id] = {
        "user_id": session_id,
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
    }
    # 在 /callback 成功后，可删除临时 session_id
    if session_id in user_sessions:
        del user_sessions[session_id]
    redirect_resp = RedirectResponse(url="/auth/success")

    redirect_resp.set_cookie(
        key="auth_session",
        value=permanent_session_id,
        httponly=True,
        secure=False,  # 本地开发用 False，生产用 True
        samesite="lax",
        max_age=3600  # 1小时
    )
    return redirect_resp
    # # 保存令牌（含 refresh_token），但不获取用户信息
    # user_sessions[session_id].update({
    #     "access_token": token_data["access_token"],
    #     "refresh_token": token_data.get("refresh_token"),
    #     "expires_in": token_data.get("expires_in"),
    #     # 注意：不再在这里设置 user
    # })
    # 重定向到 profile，由 profile 按需加载用户信息
    # return JSONResponse({"status": "success"})

@app.get("/auth/success")
async def auth_success():
    return HTMLResponse(open("html/success.html",encoding="utf-8").read())


@app.get("/profile")
def profile(request: Request):
    """显示用户信息和 OneNote 状态（按需获取用户信息）"""
    # session_id = request.cookies.get("session_id")
    # session = user_sessions.get(session_id)
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")
    # 按需获取用户信息（如果尚未缓存）
    user = session.get("user")
    if user is None:
        try:
            user_resp = requests.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {session['access_token']}"}
            )
            if user_resp.status_code == 200:
                user = user_resp.json()
                session["user"] = user  # 缓存到会话
            else:
                user = {}  # 或保留为 None，前端可处理
        except Exception:
            user = {}

    return {
        "message": "Login successful!",
        "user": user,
        "has_access_token": True,  # 此时一定有，因为上面已校验
    }


@app.get("/api/notebooks")
def get_notebooks(request: Request):
    """调用 Microsoft Graph 获取 OneNote 笔记本"""
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")

    headers = {"Authorization": f"Bearer {session['access_token']}"}
    r = requests.get("https://graph.microsoft.com/v1.0/me/onenote/notebooks", headers=headers)
    if r.status_code == 401:
        # Token 可能过期，尝试用 refresh_token 刷新（此处省略，可扩展）
        raise HTTPException(status_code=401, detail="Token expired")
    elif r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()["value"]



@app.get("/api/sections/{notebook_id}", response_model=List[OneNoteItem])
async def get_sections(notebook_id: str, request: Request):
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")
    token = session["access_token"]
    url = f"https://graph.microsoft.com/v1.0/me/onenote/notebooks/{notebook_id}/sections"
    data = onenote_request("GET", url, token)
    return data.get("value", [])


@app.get("/api/pages/{section_id}", response_model=List[OneNotePage])
def get_pages(section_id: str, request: Request):
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")
    token = session["access_token"]
    # 2. 构造正确 URL（修复空格问题）
    url = f"https://graph.microsoft.com/v1.0/me/onenote/sections/{section_id}/pages"
    data = onenote_request("GET", url, token)
    return data.get("value", [])

# @app.post("/api/note", response_model=NoteResponse)
# async def create_note(req: NoteRequest, request: Request):
#     auth_session_id = request.cookies.get("auth_session")
#     if not auth_session_id or auth_session_id not in user_sessions:
#         raise HTTPException(status_code=401, detail="Not authenticated")
#     session = user_sessions[auth_session_id]
#     if "access_token" not in session:
#         raise HTTPException(status_code=401, detail="Access token missing")
#     token = session["access_token"]
#     # note_text = generate_note_from_llm(req.text)
#     note_text = "generate_note_from_llm(req.text)"
#     page_url = sync_to_onenote(
#         token=token,
#         note_text=note_text,
#         section_id=req.section_id,
#         page_id=req.page_id,
#         create_new=req.create_new
#     )
#     return NoteResponse(note=note_text, page_url=page_url)


@app.post("/api/create-section")
def create_section(section_data:CreateSectionRequest,request: Request) -> dict:

    """
    在指定的 OneNote 笔记本中创建一个新的分区
    Returns:
        创建的分区信息

    Reference:
        https://learn.microsoft.com/zh-cn/graph/api/notebook-post-sections?view=graph-rest-1.0&tabs=http
    """
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")
    token = session["access_token"]
    section_name = section_data.displayName
    notebook_id = section_data.notebook_id
    endpoint = f"https://graph.microsoft.com/v1.0/me/onenote/notebooks/{notebook_id}/sections"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    body = {
        "displayName": section_name
    }
    try:
        response = requests.post(endpoint, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create section: {str(e)}"
        )



# 替换现有的 create_page_endpoint 函数
@app.post("/api/create-page")
async def create_page_endpoint(page_data: CreatePageRequest, request: Request):
    """
    创建新页面的API端点

    Args:
        section_id: 分区 ID
        title: 页面标题
        content: 页面内容
    """
    # 首先检查认证
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")
    token = session["access_token"]

    # 从 Pydantic 模型中获取数据
    section_id = page_data.section_id
    page_title = page_data.title
    page_content = page_data.content
    # 验证必要参数
    if not section_id:
        raise HTTPException(status_code=400, detail="Section ID is required")
    if not page_title:
        raise HTTPException(status_code=400, detail="Page title is required")
    if not page_content:
        raise HTTPException(status_code=400, detail="Page content is required")
    try:
        result = create_page(token, section_id, page_title, page_content)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# # 在需要输出日志的地方
# logger.info("这是日志信息")
# logger.error("这是错误信息")


def create_page(token: str, section_id: str, page_title: str, page_content: str) -> dict:
    """
    在指定的 OneNote 分区中创建一个新的页面

    Args:
        token: 访问令牌
        section_id: 分区 ID
        page_title: 页面标题
        page_content: 页面内容（HTML格式）

    Returns:
        创建的页面信息

    Reference:
        https://learn.microsoft.com/zh-cn/graph/api/section-post-pages?view=graph-rest-1.0&tabs=http
    """
    task="generate_page"
    endpoint = f"https://graph.microsoft.com/v1.0/me/onenote/sections/{section_id}/pages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/xhtml+xml"
    }

    # 构建页面内容（XHTML格式）
    xhtml_content = llm_generate(task,page_title=page_title,page_content=page_content)
    xhtml_content=extract_full_html(xhtml_content)

    try:
        response = requests.post(endpoint, headers=headers, data=xhtml_content.encode('utf-8'), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create page: {str(e)}"
        )



def get_page_content(token: str, page_id: str) -> str:
    """
       获取OneNote页面内容
       https://learn.microsoft.com/zh-cn/graph/api/page-get?view=graph-rest-1.0&tabs=http
       """
    endpoint = f"https://graph.microsoft.com/v1.0/me/onenote/pages/{page_id}/content"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/html"
    }
    try:
        response = requests.get(endpoint, headers=headers, timeout=10)
        response.raise_for_status()
        # 返回页面内容
        # 获取原始HTML内容
        html_content = response.text

        # 清理HTML内容，提取纯文本
        clean_content = clean_onenote_content(html_content)

        return clean_content
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to get page content: {str(e)}"
        )


def update_page_content(token: str, page_id: str, html_content: str) -> dict:
    """
    更新指定 OneNote 页面的内容

    Args:
        token: 访问令牌
        page_id: 要更新的页面 ID
        html_content: 新的 HTML 内容

    Returns:
        更新操作的结果

    Reference:
        https://learn.microsoft.com/zh-cn/graph/api/page-update?view=graph-rest-1.0&tabs=http
    """
    endpoint = f"https://graph.microsoft.com/v1.0/me/onenote/pages/{page_id}/content"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 构造更新请求体
    # 这里使用 'replace' 操作替换整个页面内容
    body = [{
        "target": "body",
        "action": "replace",
        "content": html_content
    }]

    try:
        response = requests.patch(endpoint, headers=headers, json=body, timeout=10)
        response.raise_for_status()

        # OneNote 更新操作通常返回 204 No Content
        # 根据文档，成功更新后不返回内容主体
        if response.status_code == 204:
            return {"status": "success", "message": "Page updated successfully"}
        else:
            # 如果返回了其他状态码，尝试解析 JSON 或返回通用成功消息
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"status": "success", "message": f"Page updated with status {response.status_code}"}

    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to update page: {str(e)}"
        )
@app.post("/api/page-summary")
async def generate_page_summary(request: Request, payload: dict):
    """
    生成指定页面内容摘要的API端点
    """
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")
    token = session["access_token"]
    page_id = payload.get("page_id")
    if not page_id:
        raise HTTPException(status_code=400, detail="Page ID is required")

    try:
        # 获取页面内容
        page_content = get_page_content(token, page_id)
        # 生成摘要
        xhtml_summary = llm_generate("page_abstract",page_content=page_content)


        return {"pagesummary":xhtml_summary}
    except Exception as e:
        raise (HTTPException(status_code=500, detail=str(e)))
@app.post("/api/append-page")
async def append_page(request: Request, payload: dict):
    """
    生成指定页面内容摘要的API端点
    """
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")
    token = session["access_token"]
    page_id = payload.get("page_id")
    new_content = payload.get("pageContent")
    if not page_id:
        logger.error("append not page_id")
        raise HTTPException(status_code=400, detail="Page ID is required")
    if not new_content:
        logger.error("append not new_content")
        raise HTTPException(status_code=400, detail="Page ID is required")

    try:
        # 获取页面内容
        old_note = get_page_content(token, page_id)
        # 生成摘要
        new_page = llm_generate("append_page",old_note=old_note,new_content=new_content)
        xhtml_new_page = extract_full_html(new_page)
        result=update_page_content(token,page_id,xhtml_new_page)
        return result
    except Exception as e:
        logger.error(traceback.print_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/review-questions")
async def generate_review_questions(request: Request, payload: dict):
    """
    生成指定页面内容摘要的API端点
    """
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")
    token = session["access_token"]
    page_id = payload.get("page_id")
    question_num = payload.get("question_num", 5)
    if not page_id:
        raise HTTPException(status_code=400, detail="Page ID is required")
    try:
        # 获取页面内容

        page_content = get_page_content(token, page_id)
        page_content = clean_onenote_content(page_content)
        review = llm_generate("question_generate", question_num=question_num,page_content=page_content)
        review=llm_json_parse(review)
        return {"questions":review}
    except Exception as e:
        logger.error(f"generate_review_questions错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-answers")
async def analyze_answers(request: Request, payload: dict):
    """
    分析用户答题情况并提供学习建议
    """
    logger.info(f"/api/analyze-answers处理")
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")
    token = session["access_token"]
    try:
        # 获取并解析答题数据
        answers_json = payload.get("question_a_answer")
        page_id = payload.get("page_id")
        page_content = get_page_content(token, page_id)
        page_content = clean_onenote_content(page_content)
        if not answers_json:
            raise HTTPException(status_code=400, detail="Missing question_a_answer data")
        # 解析JSON字符串为对象
        user_answers = json.loads(answers_json)
        # 调用LLM生成分析报告
        xhtml_overall_suggestions = llm_generate("answer_analysis", user_answers=user_answers,page_content=page_content)
        return AnalyzeAnswersResponse(overall_suggestions=xhtml_overall_suggestions)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
    except Exception as e:
        logger.error(f"analyze_answers错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dialogue")
async def dialogue(request: Request, payload: dict):
    """
    分析用户答题情况并提供学习建议
    """
    auth_session_id = request.cookies.get("auth_session")
    if not auth_session_id or auth_session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = user_sessions[auth_session_id]
    if "access_token" not in session:
        raise HTTPException(status_code=401, detail="Access token missing")
    token = session["access_token"]
    try:
        # 获取并解析答题数据
        user_print = payload.get("user_print")
        page_id = payload.get("page_id")
        page_content = get_page_content(token, page_id)
        page_content = clean_onenote_content(page_content)
        if not user_print:
            raise HTTPException(status_code=400, detail="Missing user_print data")
        # 解析JSON字符串为对象
        # 调用LLM生成分析报告
        dialogue = llm_generate("dialogue", user_print=user_print,page_content=page_content)
        return {"replay":dialogue}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
    except Exception as e:
        logger.error(f"analyze_answers错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


