# Pharma RAG Demo

一个面向医药呼叫中心场景的 Streamlit MVP。

## V3 Change Summary

- 保持原有 RAG 检索与 PDF 预览流程不变
- 改进日文自然问句的高亮词拆分，例如 `被害救済制度は副作用を含めているか`
- 右侧 PDF 优先按用户问题高亮，只有完全找不到时才回退到检索结果文本
- 左侧结果列表显示更直观的相似度百分比和进度条
- 为关键高亮逻辑补充了英文注释，便于后续维护

场景说明：

- 药局来电咨询某个药品问题
- 操作员输入问题后，系统从 PDF 手册中检索相关段落
- 左侧展示排序后的检索结果
- 右侧展示对应 PDF 页面，并对匹配文本绘制红框

## 目录结构

```text
pharma-rag-demo/
├── app.py
├── ingest.py
├── rag.py
├── pdf_utils.py
├── requirements.txt
├── .env.example
├── db/
└── data/
    └── manual.pdf
```

## Mac 安装步骤

1. 进入项目目录

```bash
cd  ./pharma-rag-demo
```

2. 创建并激活虚拟环境

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

4. 配置环境变量

```bash
cp .env.example .env
```

然后编辑 `.env`，填入你的 OpenAI Key：

```bash
OPENAI_API_KEY=your_openai_api_key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

5. 准备 PDF

程序默认读取 `data/manual.pdf`。

如果你当前目录里已经有 `data/000265668.pdf`，可以直接复制成默认文件名：

```bash
cp data/000265668.pdf data/manual.pdf
```

## 建库命令

首次运行前先把 PDF 向量化写入本地 ChromaDB：

```bash
python ingest.py
```

成功后会在 `./db` 下生成本地向量库。

如果遇到 `429 insufficient_quota`，说明当前 OpenAI key 的额度不足，换一个有可用额度的 key 后重新运行 `python ingest.py` 即可。

## 启动应用

```bash
streamlit run app.py
```

启动后在浏览器中打开页面：

- 左侧输入药局问题并点击 `検索`
- 选择任一检索结果
- 右侧会跳转到对应 PDF 页面并显示红框高亮

## How To Run V3

1. 进入项目目录并激活虚拟环境

```bash
cd ./pharma-rag-demo
source .venv/bin/activate
```

2. 如果是首次运行，先建库

```bash
python ingest.py
```

3. 启动 Streamlit

```bash
streamlit run app.py
```

## How To Test V3

推荐先做下面这组手工验证：

1. 在左侧输入：

```text
被害救済制度は副作用を含めているか
```

2. 点击 `検索`
3. 选择第一页结果
4. 确认右侧 PDF 页面上会出现多个红框，至少能覆盖 `被害救済制度` 和 `副作用` 相关文本
5. 确认左侧每条结果都有：
   - 页码
   - `類似度: xx.x%`
   - 相似度进度条

也可以用下面的轻量命令验证 V3 的高亮词拆分：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -c "from pathlib import Path; from pdf_utils import build_search_terms, render_annotated_page; q='被害救済制度は副作用を含めているか'; print(build_search_terms(question=q, selected_text='')); print(render_annotated_page(Path('data/manual.pdf'), 8, question=q, selected_text='')[2])"
```

## 说明

- UI 标签使用日文，便于做日语场景演示
- 代码注释使用英文，便于维护
- 该项目面向本地 demo，默认使用本地 ChromaDB 和 OpenAI Embeddings
