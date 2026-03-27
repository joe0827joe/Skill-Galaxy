import json, sqlite3, requests, csv, random, time, re, io, os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response
from dotenv import load_dotenv
import urllib3
from collections import Counter

# 關閉 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 設定管理 (擴充版) ---
DATA_DIR = "data_storage"
os.makedirs(DATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

def load_config():
    defaults = {
        "openai_api_key": "", "model_name": "gpt-4o-mini", 
        "api_base": "https://api.openai.com/v1",
        "google_search_api_key": "", "google_cse_id": ""
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f); defaults.update(data)
    return defaults

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def flatten_skills(data):
    if not isinstance(data, list): return []
    res = []
    for item in data:
        if isinstance(item, str): res.append(item)
        elif isinstance(item, dict):
            res.append(", ".join([str(v) for v in item.values()]))
        else: res.append(str(item))
    return res

def search_web(query):
    # RAG 搜索組件：優先使用 Google API，其次回退至 DuckDuckGo
    cfg = load_config()
    g_key = cfg.get("google_search_api_key")
    g_cx = cfg.get("google_cse_id")
    
    if g_key and g_cx:
        try:
            url = f"https://www.googleapis.com/customsearch/v1?key={g_key}&cx={g_cx}&q={query}"
            r = requests.get(url, timeout=10) # 寬鬆搜尋超時
            items = r.json().get('items', [])
            return "\n".join([i.get('snippet', '') for i in items[:3]])
        except Exception as e:
            print(f"Google Search Error: {e}")
            
    # 簡易網頁檢索元件 (使用 DuckDuckGo 零延遲搜尋)
    try:
        url = f"https://duckduckgo.com/html/?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        snippets = re.findall(r'<a class="result__snippet".*?>(.*?)</a>', r.text, re.DOTALL)[:3]
        return "\n".join([re.sub('<[^<]+?>', '', s) for s in snippets])
    except: return "未發現搜尋結果"

def ask_ai(prompt):
    cfg = load_config()
    if not cfg.get("openai_api_key"): return "請先在首頁設定 OpenAI API Key"
    try:
        url = f"{cfg.get('api_base', 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {cfg['openai_api_key']}", "Content-Type": "application/json"}
        body = {
            "model": cfg.get("model_name", "gpt-4o-mini"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        res = requests.post(url, headers=headers, json=body, timeout=60) # 提升至 60 秒深度報告緩衝
        return res.json()['choices'][0]['message']['content']
    except Exception as e: return f"AI 調用超時或異常 (建議檢查網路或重試): {str(e)}"

def get_llm_chain(api_key, model="gpt-4o-mini", base_url=None):
    if not api_key: return None
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        
        llm = ChatOpenAI(
            model=model, temperature=0, openai_api_key=api_key,
            base_url=base_url if base_url and base_url.strip() else "https://api.openai.com/v1"
        )
        system_msg = """你是一位專業的高階技術獵頭 (Technical Recruiter)。
任務：精煉職缺中的核心技術熱點。提取標籤並對其分類。
請務必以 JSON 格式回應，格式為列表，例如：["[雲端] AWS", "[後端] Python"]。"""
        prompt = ChatPromptTemplate.from_messages([("system", system_msg), ("user", "內容: {description}\n要求: {requirements}")])
        return prompt | llm | JsonOutputParser()
    except Exception as e:
        print(f"LLM Upgrade Error: {e}"); return None

app = Flask(__name__)

class JobScraper:
    def __init__(self):
        self.session = requests.Session(); self.session.verify = False 
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Referer': 'https://www.104.com.tw/jobs/search/',
            'Accept': 'application/json, text/plain, */*'
        }
    
    def _init_db(self, task_name):
        db_path = os.path.join(DATA_DIR, f"{task_name}.db")
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY, job_name TEXT, company TEXT,
            description TEXT, requirements TEXT, Skills_Raw TEXT,
            location TEXT, salary TEXT, link TEXT, scraped_at DATETIME
        )''')
        return conn

    def get_task_count(self, name):
        p = os.path.join(DATA_DIR, f"{name}.db")
        if not os.path.exists(p): return 0
        try:
            conn = sqlite3.connect(p)
            c = conn.execute("SELECT count(*) FROM jobs").fetchone()[0]
            conn.close(); return c
        except: return 0

    def get_detail(self, jid):
        headers = self.headers.copy()
        # 詳情頁 Referer 通常包含 jid
        headers['Referer'] = f'https://www.104.com.tw/job/{jid}'
        try:
            r = self.session.get(f'https://www.104.com.tw/api/jobs/{jid}', headers=headers, timeout=5)
            d = r.json().get('data', {})
            header = d.get('header', {})
            job_name = header.get('jobName', '')
            cust_name = header.get('custName', '')
            desc = d.get('jobDetail', {}).get('jobDescription', '')
            cond = d.get('condition', {})
            req = f"{cond.get('workExp', '')}\n{','.join(cond.get('major', []))}\n{cond.get('other', '')}"
            return job_name, cust_name, desc, req
        except: return "", "", "", ""

    def scrape_generator(self, keyword, pages=1, task_name="default"):
        try:
            from urllib.parse import quote
            cfg = load_config()
            chain = get_llm_chain(cfg.get("openai_api_key"), cfg.get("model_name"), cfg.get("api_base"))
            yield json.dumps({"status": f"🚀 引擎已啟動！"}) + '\n'
            api = 'https://www.104.com.tw/jobs/search/api/jobs'
            # 使用攔截到的實測參數
            params = {
                'jobsource': 'joblist_search',
                'keyword': keyword,
                'order': '15',
                'page': 1,
                'pagesize': '20'
            }
            
            headers = self.headers.copy()
            headers['Referer'] = f'https://www.104.com.tw/jobs/search/?jobsource=joblist_search&keyword={quote(keyword)}'
            
            try:
                r = self.session.get(api, params=params, headers=headers, timeout=12)
                data = r.json()
                # 實測 metadata 可能在 data 同級或是 data 內部
                meta = data.get('metadata', {}).get('pagination', {})
                if not meta and isinstance(data.get('data'), dict):
                    meta = data.get('data').get('metadata', {}).get('pagination', {})
                
                dt, dp = (meta.get('total', 0), meta.get('lastPage', 1))
                
                # 如果找不到 meta，但有 data list，嘗試計算
                if dt == 0:
                    d_payload = data.get('data', [])
                    if isinstance(d_payload, list) and len(d_payload) > 0:
                        dt = len(d_payload); dp = 1

                yield json.dumps({"total_jobs": dt, "total_pages_on_site": dp, "status": f"🔍 找到 {dt} 筆職缺。"}, ensure_ascii=False) + '\n'
            except Exception as e: 
                print(f"Initial Search Error: {e}")
                dt, dp = 0, 1

            limit = min(int(pages), dp) if int(pages) > 0 else dp
            if dt == 0 and limit > 0: dt = 20 # 強制嘗試

            for p in range(1, limit + 1):
                params['page'] = p
                yield json.dumps({"status": f"📡 第 {p} 頁採集中...", "current_page": p}, ensure_ascii=False) + '\n'
                try:
                    resp = self.session.get(api, params=params, headers=headers, timeout=10)
                    resp_json = resp.json()
                    
                    # 關鍵修復：處理 data 為 list 或包含 list 的情況
                    data_part = resp_json.get('data', [])
                    if isinstance(data_part, list):
                        list_data = data_part
                    elif isinstance(data_part, dict):
                        list_data = data_part.get('list', [])
                    else:
                        list_data = []
                    
                    if not list_data:
                        print(f"Empty list_data for page {p}")
                        continue

                    for j in list_data:
                        link = ""
                        if isinstance(j.get('link'), dict):
                            link = j.get('link').get('job', '')
                        else:
                            link = str(j.get('link', ''))
                            
                        jid = ""
                        if 'job/' in link:
                            jid = link.split('job/')[-1].split('?')[0]
                        elif link:
                            # 處理 //www.104.com.tw/job/77phe 這種情況
                            jid = link.strip('/').split('/')[-1].split('?')[0]
                            
                        if not jid: continue
                        
                        job_name_api, cust_name_api, desc, req = self.get_detail(jid)
                        job_name = job_name_api or j.get('jobName')
                        cust_name = cust_name_api or j.get('custName')
                        
                        salary = j.get('salaryDesc', '面議')
                        loc = (j.get('jobAddrNoDesc', '') + j.get('jobAddress', '')) or '台灣'
                        
                        skills_raw = []
                        if chain:
                            try: 
                                raw = chain.invoke({"description": desc[:800], "requirements": req[:800]})
                                skills_raw = flatten_skills(raw)[:10]
                            except Exception as e: 
                                print(f"LLM Invoke Error: {e}")
                                skills_raw = ["解析失敗"]
                        
                        conn = self._init_db(task_name)
                        full_link = link if link.startswith('http') else 'https:' + link
                        conn.execute('''INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)''',
                                     (jid, job_name, cust_name, desc, req, " | ".join(skills_raw), loc, salary, full_link, datetime.now()))
                        conn.commit(); conn.close()
                        yield json.dumps({
                            'job_name': job_name, 
                            'company': cust_name, 
                            'Skills_Raw': skills_raw,
                            'salary': salary,
                            'location': loc,
                            'description': desc,
                            'requirements': req,
                            'link': full_link
                        }, ensure_ascii=False) + '\n'
                        time.sleep(random.uniform(1.0, 2.0))
                except Exception as e: 
                    print(f"Page {p} Error: {e}")
                    break
            yield json.dumps({"status": "🏁 採集完成"}) + '\n'
        except Exception as e: yield json.dumps({"error": str(e)}) + '\n'

scraper = JobScraper()

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST': save_config(request.json); return jsonify({"status": "Success"})
    return jsonify(load_config())

@app.route('/analytics/<name>')
def analytics_page(name): return render_template('analytics.html', task_name=name)

@app.route('/api/tasks/<name>/stats', methods=['GET'])
def get_task_stats(name):
    db_file = os.path.join(DATA_DIR, f"{name}.db")
    if not os.path.exists(db_file): return jsonify({"skills": {}, "edges": []}), 404
    try:
        conn = sqlite3.connect(db_file); rows = conn.execute("SELECT Skills_Raw FROM jobs").fetchall(); conn.close()
        counter = Counter(); relations = Counter(); skill_to_cat = {}; job_tags_list = []
        for r in rows:
            if r[0]:
                raw = r[0].split(" | "); names = []
                for t in raw:
                    cat = t.split("]")[0].replace("[", "").strip() if "]" in t else "一般"
                    body = t.split("] ")[-1] if "]" in t else t
                    # 增強型二維解析：即使標籤內包含逗號，也將其拆解為獨立技術節點
                    parts = re.split(r'[,，、/]', body)
                    for p in parts:
                        core = p.strip()
                        if core: 
                            names.append(core)
                            skill_to_cat[core] = cat
                job_tags_list.append(list(set(names)))
                for t in set(names): counter[t] += 1
        
        top_skills_data = {}
        top_names = [s for s, _ in counter.most_common(25)]
        for name in top_names: top_skills_data[name] = {"count": counter[name], "cat": skill_to_cat.get(name, "一般")}

        for tags in job_tags_list:
            relevant = [t for t in tags if t in top_skills_data]
            for i in range(len(relevant)):
                for j in range(i + 1, len(relevant)):
                    pair = tuple(sorted((relevant[i], relevant[j])))
                    relations[pair] += 1
        return jsonify({"skills": top_skills_data, "edges": [{"from": p[0], "to": p[1], "width": w} for p, w in relations.items() if w > 0]})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/skills/<name>/summary', methods=['GET'])
def skill_summary(name):
    try:
        res = ask_ai(f"請用繁體中文一句話介紹技術『{name}』在職場的定位。")
        return jsonify({"summary": res})
    except: return jsonify({"summary": "市場實戰技術"})

@app.route('/api/skills/<name>/deep_dive', methods=['GET'])
def skill_deep_dive(name):
    try:
        search_res = search_web(f"{name} 技術定義 職場定位")
        prompt = f"針對『{name}』，結合：{search_res}，用 Markdown 格式產出深度報告：### 技術定義, ### 職場價值分析, ### 學習建議。"
        return jsonify({"report": ask_ai(prompt)})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/tasks/<name>/data', methods=['GET'])
def get_task_data(name):
    db_file = os.path.join(DATA_DIR, f"{name}.db")
    if not os.path.exists(db_file): return jsonify([]), 404
    conn = sqlite3.connect(db_file); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM jobs ORDER BY scraped_at DESC").fetchall(); conn.close()
    return jsonify([{
        'job_name': r['job_name'], 
        'company': r['company'], 
        'Skills_Raw': r['Skills_Raw'].split(" | ") if r['Skills_Raw'] else [], 
        'salary': r['salary'], 
        'location': r['location'], 
        'link': r['link'],
        'description': r['description'],
        'requirements': r['requirements']
    } for r in rows])

@app.route('/api/tasks/<name>', methods=['DELETE'])
def delete_task(name):
    db_file = os.path.join(DATA_DIR, f"{name}.db")
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            return jsonify({"status": "Success"})
        except Exception as e:
            return jsonify({"status": "Error", "message": str(e)}), 500
    return jsonify({"status": "Not Found"}), 404

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    tasks = []
    if os.path.exists(DATA_DIR):
        for f in os.listdir(DATA_DIR):
            if f.endswith('.db'):
                n = f.replace('.db', ''); c = scraper.get_task_count(n)
                tasks.append({'name': n, 'count': c})
    return jsonify(tasks)

@app.route('/api/scrape', methods=['POST'])
def run_scrape(): r = request.json; return Response(scraper.scrape_generator(r['keyword'], int(r['pages']), r['task_name']), mimetype='application/json')

@app.route('/api/export/<task_name>')
def export_full_db(task_name):
    db_file = os.path.join(DATA_DIR, f"{task_name}.db")
    if not os.path.exists(db_file): return "Task not found", 404
    conn = sqlite3.connect(db_file); conn.row_factory = sqlite3.Row
    js = conn.execute("SELECT * FROM jobs").fetchall(); conn.close()
    output = io.StringIO(); output.write('\ufeff')
    keys = ['job_name', 'company', 'Skills_Raw', 'salary', 'location', 'link', 'scraped_at']
    writer = csv.DictWriter(output, fieldnames=keys); writer.writerow({k: v for k, v in zip(keys, ['職稱','公司','Skills_Raw','薪資','地點','連結','時間'])})
    for r in js: writer.writerow({k: r[k] for k in keys})
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name=f'{task_name}.csv')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
