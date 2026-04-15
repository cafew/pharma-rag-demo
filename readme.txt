


Please inspect the current repo first and summarize:
1) project structure
2) app entry point
3) where PDF loading happens
4) where vector search happens
5) where page rendering / red-box annotation happens

Then fix this issue with minimal changes only:
    比如检索副作用，现场红色框表示的地方，还有URL链接，不想关的部分等
    另外，检索结果的列表里面，能否给出类似度等，目前就是列表，不知道哪个最相关等
    
After the fix:
- run the relevant command
- show me which files changed
- explain why the bug happened



3）Mac 上先建项目
    mkdir pharma-rag-demo
    cd pharma-rag-demo
    
    python3 -m venv .venv
    source .venv/bin/activate
    
    cat > requirements.txt <<'EOF'
    streamlit
    openai
    chromadb
    pymupdf
    pypdf
    python-dotenv
    pandas
    numpy
    EOF
    
    mkdir -p data db

把 key 放环境变量
    echo 'export OPENAI_API_KEY="你的新key"' >> ~/.zshrc
    source ~/.zshrc
    echo $OPENAI_API_KEY
    
    
    结论：先做 Mac 本地 MVP：Streamlit + ChromaDB + PyMuPDF + OpenAI Embeddings。别先上 EC2；先跑通“检索→点结果→右侧跳页+红框”。另外，你刚贴出的 API key 已暴露，先立刻 rotate，且以后只放环境变量。 ￼

依据
	1.	Codex 适合在 macOS 的本地工具里直接建项目、改文件、跑命令；先本地做完再搬到服务器，阻力最小。 ￼
	2.	OpenAI 官方明确建议：API key 不要分享、不要写进代码或前端，要放环境变量；团队协作优先用 project-based key。 ￼

你这个 Demo，建议这样做：

1）先定 MVP 方案

不要一开始就做“真正 PDF viewer + 原生高亮插件”。
最快可交付的是：
	•	左侧：问题输入框 + Top 5 检索结果
	•	右侧：把 PDF 指定页渲染成图片
	•	点击左侧结果后：
	•	跳到对应页
	•	用红框框出命中的文字区域

这条路在 Streamlit 里最稳，因为 PyMuPDF 很容易拿到页码和文字框坐标。

你上传的样本 PDF 已经很适合做首个 demo；例如第 5–6 页就有“重症高血圧”的副作用说明、症状和早期 대응点，拿来做“副作用是什么”检索非常合适。 ￼

⸻

2）项目目录

先做成这个结构：

pharma-rag-demo/
├─ app.py
├─ ingest.py
├─ rag.py
├─ pdf_utils.py
├─ requirements.txt
├─ .env.example
├─ README.md
├─ data/
│  └─ manual.pdf
└─ db/


⸻

3）Mac 上先建项目

在终端：

mkdir pharma-rag-demo
cd pharma-rag-demo

python3 -m venv .venv
source .venv/bin/activate

cat > requirements.txt <<'EOF'
streamlit
openai
chromadb
pymupdf
pypdf
python-dotenv
pandas
numpy
EOF

mkdir -p data db

把你的 PDF 放到：

data/manual.pdf

然后把 key 放环境变量，不要写死在代码里。OpenAI 官方建议变量名就用 OPENAI_API_KEY。 ￼

echo 'export OPENAI_API_KEY="你的新key"' >> ~/.zshrc
source ~/.zshrc
echo $OPENAI_API_KEY


⸻

4）先让 Codex 帮你一次性生成骨架

把下面这段直接贴给 Codex：

Create a runnable Streamlit MVP for a pharmaceutical call-center RAG demo.

Goal:
- A call-center operator receives a question from a pharmacy about a medicine.
- The app must quickly retrieve relevant sections from a PDF manual and show the source page.
- Left pane: question input + ranked retrieval results.
- Right pane: show the selected PDF page.
- When a result is clicked, jump to that page and draw red rectangles around matched text.

Tech stack:
- Python 3.11
- Streamlit
- ChromaDB for local vector store
- OpenAI embeddings via OPENAI_API_KEY from environment variables
- PyMuPDF for PDF text extraction, page rendering, and bounding boxes
- python-dotenv optional for local development

Files to generate:
- requirements.txt
- ingest.py
- rag.py
- pdf_utils.py
- app.py
- README.md
- .env.example

Functional requirements:
1. ingest.py
   - Load PDF from data/manual.pdf
   - Extract text page by page
   - Chunk by paragraph with overlap
   - Store metadata: page_number, chunk_id, source_file, text
   - Create embeddings and save to local ChromaDB under ./db

2. rag.py
   - Query ChromaDB
   - Return top_k results with score, text snippet, page number

3. pdf_utils.py
   - Render a PDF page to image
   - Search for query keywords on the selected page using PyMuPDF
   - Draw red rectangles on matched areas
   - Return the annotated image

4. app.py
   - Streamlit wide layout
   - Left column:
     - title
     - text_input for question
     - search button
     - ranked results list
     - each result shows snippet + page number + score
     - clicking a result updates session state:selected_page and selected_text
   - Right column:
     - show annotated PDF page image
     - page navigation buttons
   - Japanese UI labels

5. README.md
   - setup instructions for Mac
   - commands to ingest and run

Keep code simple, clean, and demo-friendly.
Use comments and error handling.


⸻

5）你真正要实现的核心逻辑

很简单，只有 4 步：

A. ingest.py
	•	读 PDF
	•	按页抽文字
	•	切 chunk
	•	每个 chunk 记住：
	•	page_number
	•	text
	•	source_file
	•	生成 embedding 后写入 ChromaDB

B. rag.py
用户问：
副作用是什么？

然后：
	•	embed 这个问题
	•	去 ChromaDB 相似检索
	•	返回前 5 条：
	•	摘要
	•	页码
	•	分数

C. pdf_utils.py
当用户点了某条结果：
	•	取它的 page_number
	•	用 PyMuPDF 打开该页
	•	page.search_for(关键词) 找文字坐标
	•	画红框
	•	渲染成图片给 Streamlit 显示

D. app.py
	•	左边搜
	•	左边点结果
	•	右边刷新对应页图片

⸻

6）关于“红框”怎么做

这里最重要。

你不要先追求“在浏览器里的原生 PDF 上高亮”。
Demo 阶段最稳的做法：
	1.	右侧显示“PDF 页图片”
	2.	不是直接嵌 PDF viewer
	3.	用 PyMuPDF 在图片上画红框后再显示

这样你 1 天内就能做出来。

实现思路：

page = doc[page_no]
rects = page.search_for(keyword)
pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
# 再把 rects 画到图上


⸻

7）检索结果建议长这样

左侧不要只放一句话，最好每条都带 4 个字段：
	•	排名
	•	摘要前 120 字
	•	Page 号
	•	相似度分数

例如：

1. 重症高血圧では頭痛、胸の痛み、息切れ...
   Page 5 | score: 0.87

2. 高血圧とは？初期症状、早期発見と早期対応...
   Page 6 | score: 0.81


⸻

8）先别做的东西

第一版先不要加：
	•	多 PDF 管理
	•	用户登录
	•	真正药品名 NER
	•	回答生成总结
	•	权限系统
	•	云端向量库

先只做 “找到哪一页哪一段”。
这个对呼叫中心 Demo 已经够强。

⸻

9）搬到公司 EC2 时怎么想

本地和 EC2 尽量保持一致：
	•	同样的 Python 版本
	•	同样的 requirements.txt
	•	API key 仍然只走环境变量
	•	data/ 和 db/ 分离
	•	启动命令保持一致

部署前只要确认 4 件事：
	1.	EC2 能访问 OpenAI API
	2.	PDF 文件路径固定
	3.	db/ 目录可写
	4.	Streamlit 端口开放给内网或反向代理

⸻

10）你下一步就做这 3 件事
	1.	先 rotate 你刚贴出来的 key。OpenAI 官方建议一旦怀疑泄露就立即轮换，而且不要共享。 ￼
	2.	在 Mac 上按上面目录建空项目。
	3.	把那段英文 prompt 贴给 Codex，让它一次性生成 6 个文件。

下一条我直接给你一套可运行的最小版代码：app.py / ingest.py / rag.py / pdf_utils.py / requirements.txt。