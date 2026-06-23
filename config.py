import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
VAULT_PATH = Path(os.getenv("VAULT_PATH", r"VAULT_PATH_PLACEHOLDER"))
DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).parent / "knowledge.db"))

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

MAX_DURATION_MINUTES = 40       # videos longer than this are skipped
TRUNCATE_CHARS = 12000          # transcript chars sent to Claude
MAX_RETRIES = 4                 # Anthropic API retry attempts

# Platforms where we can detect a video but cannot extract subtitles/text.
# Returned as UnsupportedSourceError with a clear message instead of a generic failure.
UNSUPPORTED_VIDEO_HOSTS = {
    "twitter.com", "www.twitter.com", "x.com", "www.x.com",
    "instagram.com", "www.instagram.com",
    "tiktok.com", "www.tiktok.com",
    "twitch.tv", "www.twitch.tv",
    "facebook.com", "www.facebook.com", "fb.watch",
}

ALLOWED_TAGS = [
    # Tech & Engineering
    "distributed-systems", "databases", "algorithms", "data-structures",
    "machine_learning", "backend", "frontend", "architecture", "security",
    "devops", "development", "automation", "workflow",
    # Design
    "figma", "photoshop", "obsidian", "programms_motion_design",
    "ux", "ui", "ux_ui_design", "ux_research", "graphic_design",
    "product_design", "brand_design", "design_system",
    "motion_design", "typography", "color", "composition",
    "branding", "illustration", "animation", "rendering", "texture",
    "print", "digital-art", "DIY",
    # Product & Work
    "product_management", "team_workflows", "organize_my_workday",
    "career", "interview_prep", "portfolio", "freelance",
    "talks_with_designers", "sales", "marketing", "advertising", "seo",
    "personal_branding", "instagram_marketing",
    # Content & Learning
    "tutorial", "inspiration", "creative_process", "creative_resources",
    "content_creation", "video_production", "web_design",
    # Trends & Research
    "trend_analysis", "design_trends", "AI", "artificial intelligence",
    # Culture & Other
    "psychology", "sociology", "culture", "cultural_identity", "identity",
    "sustainability", "social_media", "collaboration",
    "self_assessment", "personality",
    "anime", "manga", "gaming", "restaurant", "local_business",
    "consumer_behavior",
]

# Flat list of all folders Claude can choose from.
# Prefix numbers control sort order inside product/ in Obsidian.
# Value is the path relative to VAULT_PATH.
VAULT_FOLDERS = {
    # Tools
    "figma":                    "figma",
    "photoshop":                "photoshop",
    "tilda":                    "tilda",
    "wordpress":                "wordpress",
    "notion":                   "notion",
    "obsidian":                 "obsidian",
    "claude":                   "claude",
    "cursor":                   "cursor",
    "others_AI":                "others_AI",
    "programms_motion_design":  "programms_motion_design",
    # Work
    "interview_prep":           "work/interview_prep",
    "career":                   "work/career",
    "linkedin":                 "work/linkedin",
    "portfolio":                "work/portfolio",
    "freelance":                "work/freelance",
    "talks_with_designers":     "work/talks_with_designers",
    # Product disciplines (numbered for sort order)
    "organize_my_workday":      "product/00_organize_my_workday",
    "team_workflows":           "product/00_team_workflows",
    "product_management":       "product/01_product_management",
    "ux_research":              "product/02_ux_research",
    "brand_design":             "product/03_brand_design",
    "tech_leading":             "product/04_tech_leading&architecture",
    "devops":                   "product/05_devops",
    "analysis":                 "product/06_analysis",
    "data_analysis":            "product/06_data_analysis",
    "prod_analysis":            "product/06_prod_analysis",
    "product_design":           "product/07_product_design",
    "design_system":            "product/08_design_system",
    "ux_ui_design":             "product/09_ux_ui_design",
    "graphic_design":           "product/10_graphic_design",
    "beautiful_youtube_covers":  "product/10_graphic_design/beautiful_youtube_covers",
    "references":               "product/10_graphic_design/references",
    "mockups":                  "product/10_graphic_design/mockups",
    "typography":               "product/10_graphic_design/typography",
    "colors":                   "product/10_graphic_design/colors",
    "print_design":             "product/10_graphic_design/print_design",
    "prepress":                 "product/10_graphic_design/prepress",
    "motion_design":            "product/11_motion_design",
    "ux_research_users":        "product/12_ux_research&users(test_prototype)",
    "html_css":                 "product/13_html_css",
    "development":              "product/14_development",
    "qa":                       "product/15_QA(test_beta)",
    "marketing":                "product/16_marketing",
    "sales":                    "product/17_sales",
    # Misc
    "tablet_for_design":        "tablet_for_design",
    "DIY":                      "DIY",
    "psychology":               "psychology",
    "architecture":             "architecture",
    "inbox":                    "inbox",
}

if not ANTHROPIC_API_KEY:
    raise EnvironmentError("ANTHROPIC_API_KEY не задан в .env")
