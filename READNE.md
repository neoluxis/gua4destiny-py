# Gua4Destiny Python

一个基于 Python 的易经卦象工具。目前支持了伏羲先天六十四卦和周易后天六十四卦。

## 配置

```bash
cp .env.example .env
vim .env
```

需配置 OpenAI 相关参数：
- `OPENAI_BASE_URL`：OpenAI API 的基础 URL，默认为 `https://api.openai.com/v1`。
- `OPENAI_MODEL`：使用的 OpenAI 模型，默认为 `gpt-4-0613`。
- `OPENAI_KEY`：你的 OpenAI API 密钥。

## 运行 

**使用 Docker Compose**:
```bash
docker compose up -d
```

**使用 Python**:
```bash
python -m venv venv
source venv/bin/activate  # Linux/MacOS
venv\Scripts\activate  # Windows

pip install -r requirements.txt
python main.py
```

之后打开 http://localhost:8000/ui 即可访问.
