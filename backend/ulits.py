import json
import os
import re

from bs4 import BeautifulSoup
from fastapi import HTTPException,status
from json_repair import json_repair
from openai import OpenAI

from prompt import prompt_template
from dotenv import load_dotenv

# 允许 Chrome Extension 调用

# 加载环境变量
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("BASE_URL")  # 可通过 OAuth2 获取
MODEL = os.getenv("MODEL")  # 可通过 OAuth2 获取
openai_client = OpenAI(api_key=OPENAI_API_KEY,base_url=BASE_URL)

def llm_generate(task,**params):
    now_prompt=prompt_template[task]
    now_prompt=now_prompt.format(**params)
    #调用LLM进行响应
    try:
        response = openai_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": now_prompt}
            ],
            temperature=0.7,
            timeout=30
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OpenAI error: {str(e)}"
        )


def clean_onenote_content(html_content: str) -> str:
    """
    清理OneNote页面HTML内容，提取纯文本内容用于AI分析
    """
    # 使用BeautifulSoup解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # 移除不需要的标签和内容
    # 移除样式和脚本标签
    for tag in soup(["style", "script", "meta", "link"]):
        tag.decompose()

    # 提取文本内容
    text = soup.get_text()

    # 清理多余空白字符
    text = re.sub(r'\n\s*\n', '\n\n', text)  # 合并多个空行
    text = re.sub(r'[ \t]+', ' ', text)  # 合并多个空格
    text = text.strip()

    return text
def llm_json_parse(content):
    pattern = r"```json(.*?)```"
    # 使用 findall 获取所有匹配项，并使用 re.DOTALL 标志
    matches = re.findall(pattern, content, re.DOTALL)
    # 解析 JSON 字符串
    if matches:
        content = matches[0]
    content = json.loads(json_repair.repair_json(content, ensure_ascii=False))
    return content

def extract_full_html(text: str) -> str:
    """
    从输入文本中提取第一个完整的 HTML 文档（从 <!DOCTYPE html> 或 <html> 开始，到 </html> 结束）。

    返回：
        - 提取出的完整 HTML 字符串
        - 如果未找到，返回空字符串
    """
    # 尝试匹配标准 HTML 文档（支持带或不带 DOCTYPE）
    pattern = r'(<!DOCTYPE html\s*>?\s*<html[^>]*>.*?</html>)'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # 2. 如果没有 DOCTYPE，尝试匹配 <html>...</html>
    pattern2 = r'(<html[^>]*>.*?</html>)'
    match2 = re.search(pattern2, text, re.DOTALL | re.IGNORECASE)
    if match2:
        return match2.group(1).strip()

    # 3. 如果没有 <html>，尝试匹配 <body>...</body>
    pattern3 = r'(<body>.*?</body>)'
    match3 = re.search(pattern3, text, re.DOTALL | re.IGNORECASE)
    if match3:
        return match3.group(1).strip()

    # 4. 都不匹配，返回原文本
    return text
if __name__=="__main__":
    result=llm_generate("question_generate", question_num=5,page_content="ssss")
    html="""
    ```html
<!DOCTYPE html>
<html>
  <head>
    <title>page_title</title>
    <meta name="created" content="创建时间" />
  </head>
  <body>
    笔记内容
  </body>
</html>
```
    """
    # result=extract_full_html(html)
    print(result)
    #
