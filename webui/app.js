// webui/app.js — 清晰、可维护、现代风格的前端逻辑
(() => {
  const $ = id => document.getElementById(id);

  const questionInput = $('question');
  const generateBtn = $('generate');
  const newBtn = $('new');
  const analysisEl = $('analysis');
  const guaName = $('gua-name');
  const guaImage = $('gua-image');
  const greetingEl = $('greeting');

  // 常见默认问题（用于随机填入 placeholder）
  const defaultQuestions = [
    '今天运势如何？',
    '我近期事业如何？',
    '感情运势怎样？',
    '财运会好吗？',
    '考试/面试会顺利吗？',
    '出行会顺利吗？',
    '健康状况如何？',
    '我和某人关系如何？',
    '这个项目/计划会成功吗？',
    '未来一周的总体运势？',
  ];

  function chooseRandomPlaceholder() {
    const q = defaultQuestions[Math.floor(Math.random() * defaultQuestions.length)];
    if (questionInput) questionInput.placeholder = q;
  }

  // 分时段问候（避免早上显示晚安等不合时宜的问候）
  const greetingsByPeriod = {
    morning: [
      '早上好，愿你今天顺遂。',
      '早安，开始美好的一天吧。',
      '早起的你，会有好运。'
    ],
    afternoon: [
      '午安，愿好运相随。',
      '午后安好，休息片刻再继续。'
    ],
    evening: [
      '晚上好，放松心情再问。',
      '夜色温柔，静心问事。'
    ],
    night: [
      '夜深了，适合反思与沉淀。',
      '晚安，祝你好梦。'
    ],
    anytime: [
      '愿你心想事成。',
      '安好，试着问一个具体的问题吧。',
      '祝你天天好心情。'
    ]
  };

  function getTimePeriod() {
    const h = new Date().getHours();
    if (h >= 5 && h < 12) return 'morning';
    if (h >= 12 && h < 18) return 'afternoon';
    if (h >= 18 && h < 23) return 'evening';
    return 'night';
  }

  function chooseRandomGreeting() {
    const textEl = greetingEl ? greetingEl.querySelector('.greeting__text') : null;
    if (!textEl) return;
    const period = getTimePeriod();
    const pool = (greetingsByPeriod[period] && greetingsByPeriod[period].length) ? greetingsByPeriod[period] : greetingsByPeriod.anytime;
    const i = Math.floor(Math.random() * pool.length);
    textEl.textContent = pool[i] || '';
  }

  // Toast helper: 在右下角显示提示信息（type: 'error'|'warn'|'info'）
  const toastContainer = $('toast-container');
  function showToast(message, type = 'error', timeout = 4500) {
    if(!toastContainer) return; // 容错
    const el = document.createElement('div');
    const cls = type === 'error' ? 'toast--error' : (type === 'warn' ? 'toast--warn' : 'toast--info');
    el.className = 'toast ' + cls;
    el.setAttribute('role','alert');
    el.innerHTML = `<span class="toast__msg">${String(message)}</span><button class="toast__close" aria-label="关闭">×</button>`;
    const closeBtn = el.querySelector('.toast__close');
    const remove = () => {
      el.classList.remove('toast--show');
      setTimeout(()=>{ try{ toastContainer.removeChild(el); }catch(e){} }, 260);
    };
    closeBtn.addEventListener('click', remove);
    // 先插入 DOM（初始为未显示状态），再触发显示类以实现滑入动画
    toastContainer.appendChild(el);
    // 强制回流再添加 show
    requestAnimationFrame(()=>{ el.classList.add('toast--show'); });
    // 自动关闭
    setTimeout(remove, timeout);
  }

  let currentController = null;
  let isStreaming = false;
  let apiConnected = false;

  function updateGenerateButton() {
    if (isStreaming) {
      generateBtn.textContent = '止之';
      generateBtn.classList.add('btn--warn');
      generateBtn.disabled = false;
    } else {
      generateBtn.textContent = '卜之';
      generateBtn.classList.remove('btn--warn');
      generateBtn.disabled = false;
    }
  }

  function setLoading(loading) {
    // keep newBtn disabled while loading; generate button label controlled by streaming state
    newBtn.disabled = loading;
    if (!isStreaming) {
      generateBtn.disabled = loading;
      generateBtn.textContent = loading ? '解析中…' : '卜之';
    }
  }

  async function generateGua(question) {
    // 先请求生成卦
    const resp = await fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({})});
    if(!resp.ok) {
      const text = await resp.text();
      showToast('生成卦失败: ' + (text || resp.statusText), 'error');
      throw new Error('生成卦失败');
    }
    const data = await resp.json();
    return data;
  }

  async function renderGuaImage(yaos) {
    // 请求 svg 并内联到页面，以保持清晰度
    const resp = await fetch('/api/image?format=svg', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({yaos})});
    if(!resp.ok) {
      const text = await resp.text();
      showToast('加载图片失败: ' + (text || resp.statusText), 'error');
      throw new Error('加载图片失败');
    }
    const svgText = await resp.text();
    guaImage.innerHTML = svgText;
  }

  function appendAnalysis(text) {
    analysisEl.value += text;
    analysisEl.scrollTop = analysisEl.scrollHeight;
  }

  function clearAnalysis() { analysisEl.value = ''; }

  async function streamResolve(question, yaos) {
    // 使用 fetch 的可读流来消费 SSE（后端以 text/event-stream 返回）
    currentController = new AbortController();
    const signal = currentController.signal;

    let resp;
    try {
      resp = await fetch('/api/stream', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({question, yaos}),
        signal,
      });
    } catch (e) {
      currentController = null;
      showToast('流式连接失败：' + (e.message || e), 'error');
      throw e;
    }

    if(!resp.ok) {
      const text = await resp.text();
      showToast('流式请求失败: ' + (text || resp.statusText), 'error');
      currentController = null;
      throw new Error('流式请求失败');
    }

    isStreaming = true;
    updateGenerateButton();

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while(true) {
        const {done, value} = await reader.read();
        if(done) break;
        buffer += decoder.decode(value, {stream:true});
        // SSE 事件以 \n\n 分割
        let idx;
        while((idx = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          // 每行可能形如: data: {"text":"..."}
          const lines = raw.split(/\r?\n/);
          for(const line of lines) {
            if(line.startsWith('data:')) {
              const jsonText = line.slice(5).trim();
              try {
                const obj = JSON.parse(jsonText);
                if(obj && obj.text) appendAnalysis(obj.text);
              } catch(e) {
                // 忽略解析错误
              }
            }
          }
        }
      }
    } catch (err) {
      if (signal.aborted) {
        showToast('已停止接收流式输出', 'warn');
      } else {
        showToast('流式读取出错：' + (err.message || err), 'error');
      }
    }

    // 如果剩余 buffer 包含 data 片段，尝试解析
    if(buffer.trim()) {
      const m = buffer.match(/data: (.*)/);
      if(m) {
        try { const obj = JSON.parse(m[1]); if(obj.text) appendAnalysis(obj.text); } catch(e){}
      }
    }

    currentController = null;
    isStreaming = false;
    updateGenerateButton();
  }

  async function onGenerate(e) {
    try {
      // 如果正在流式接收，点击卜之即为止之（这里不应被触发，因为按钮由 updateGenerateButton 控制）
      setLoading(true);
      clearAnalysis();
      guaImage.innerHTML = '';
      guaName.textContent = '——';

      // 如果没有输入，则使用 placeholder 自动提交
      const question = (questionInput.value || '').trim() || (questionInput.placeholder || '');
      const gua = await generateGua(question);
      guaName.textContent = gua.name;

      // yaos 服务器返回为对象数组{name,value}，我们传 value 列表回去
      const yaos = gua.yaos.map(y => y.value);
      // 渲染 SVG
      await renderGuaImage(yaos);

      // 启动流式解析并把输出追加到 text area
      await streamResolve(question, yaos);
    } catch(err) {
      console.error(err);
      appendAnalysis('\n[错误] ' + (err.message || err));
      showToast(err.message || String(err), 'error');
    } finally {
      setLoading(false);
    }
  }

  function onNew(e) {
    // 取消当前流（若存在），并重置 UI
    if(currentController) {
      currentController.abort();
      currentController = null;
    }
    questionInput.value = '';
    // 切换为另一个随机 placeholder & 问候语
    chooseRandomPlaceholder();
    chooseRandomGreeting();
    clearAnalysis();
    guaImage.innerHTML = '';
    guaName.textContent = '——';
    generateBtn.disabled = false;
  }

  // 点击行为：若正在流式接收，则停止；否则触发生成
  generateBtn.addEventListener('click', (ev) => {
    if (isStreaming) {
      if (currentController) currentController.abort();
      isStreaming = false;
      updateGenerateButton();
      showToast('已停止接收流式输出', 'warn');
      return;
    }
    onGenerate(ev);
  });

  newBtn.addEventListener('click', onNew);

  // 快捷：回车触发产生一卦
  questionInput.addEventListener('keydown', (ev) => {
    if(ev.key === 'Enter') { ev.preventDefault(); onGenerate(); }
  });

  // Health check: show connected/disconnected toast
  let lastHealthy = null;
  async function checkHealth() {
    try {
      const r = await fetch('/', {method: 'GET'});
      const healthy = r.ok;
      if (healthy && !lastHealthy) showToast('API 已连接', 'info', 1800);
      if (!healthy && lastHealthy) showToast('API 断开', 'error', 4000);
      lastHealthy = healthy;
    } catch (e) {
      if (lastHealthy || lastHealthy === null) showToast('API 断开', 'error', 4000);
      lastHealthy = false;
    }
  }
  checkHealth();
  setInterval(checkHealth, 8000);

  // 页面初始随机 placeholder 与问候语
  chooseRandomPlaceholder();
  chooseRandomGreeting();

})();
