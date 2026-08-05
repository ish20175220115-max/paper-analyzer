import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PAPERS_DIR = DATA_DIR / "papers"
REPORTS_DIR = DATA_DIR / "reports"

# 确保数据目录存在
PAPERS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_PRO_MODEL = os.getenv("DEEPSEEK_PRO_MODEL", "deepseek-v4-pro")
DEEPSEEK_FLASH_MODEL = os.getenv("DEEPSEEK_FLASH_MODEL", "deepseek-v4-flash")

# 使用 Flash 模型的分析维度（key 列表）
FLASH_DIMENSION_KEYS = {"research_question", "limitations", "methodology"}

# 访问控制（设为空字符串则不启用）
ACCESS_KEY = os.getenv("ACCESS_KEY", "")

# 论文内容限制
MIN_CONTENT_LENGTH = 200        # 最少 200 字符
MAX_CONTENT_LENGTH = 200_000    # 最多 20 万字符
