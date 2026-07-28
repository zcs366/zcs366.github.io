#!/usr/bin/env python3
"""
Hexo → Ghost 镜像同步脚本

用法：
  1. 先设环境变量:
     export GHOST_URL=http://localhost:2368
     export GHOST_ADMIN_KEY=your_admin_api_key
  
  2. 运行:
     python3 sync-to-ghost.py
  
  从 Hexo source/_posts/ 读取 Markdown 文件，
  通过 Ghost Admin API 同步到 Ghost。
  
  Admin Key 获取: Ghost后台 → Settings → Advanced → Integrations → Add custom integration
"""

import os
import sys
import json
import re
import frontmatter  # pip install python-frontmatter
import requests
from pathlib import Path
from html import escape

GHOST_URL = os.environ.get("GHOST_URL", "http://localhost:2368")
GHOST_ADMIN_KEY = os.environ.get("GHOST_ADMIN_KEY", "")
HEXO_POSTS_DIR = os.path.expanduser("~/projects/blog/source/_posts")

def generate_jwt_token():
    """Generate a Ghost Admin API JWT token from the Admin API key."""
    if not GHOST_ADMIN_KEY:
        print("❌ 未设置 GHOST_ADMIN_KEY")
        print("   获取: Ghost后台 → Settings → Advanced → Integrations → Add custom integration")
        sys.exit(1)
    
    # Ghost Admin API key format: {id}:{secret}
    parts = GHOST_ADMIN_KEY.split(":")
    if len(parts) != 2:
        print("❌ GHOST_ADMIN_KEY 格式不对，应该是 id:secret")
        sys.exit(1)
    
    key_id, key_secret = parts
    
    import jwt
    import time
    
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + 5 * 60,
        "aud": "/admin/"
    }
    
    token = jwt.encode(payload, bytes.fromhex(key_secret), algorithm="HS256", headers={"kid": key_id})
    return token


def markdown_to_ghost_html(md_content):
    """Convert simple Markdown to Ghost-compatible HTML."""
    import markdown2
    html = markdown2.markdown(md_content, extras=["fenced-code-blocks", "tables"])
    return html


def parse_hexo_post(filepath):
    """Parse a Hexo Markdown post with frontmatter."""
    with open(filepath, "r", encoding="utf-8") as f:
        post = frontmatter.load(f)
    
    title = post.get("title", Path(filepath).stem)
    date = str(post.get("date", ""))[:10]
    tags = post.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    categories = post.get("categories", [])
    if isinstance(categories, str):
        categories = [categories]
    
    content = post.content
    html = markdown_to_ghost_html(content)
    
    return {
        "title": title,
        "date": date,
        "tags": tags,
        "categories": categories,
        "html": html,
        "slug": Path(filepath).stem,
    }


def post_to_ghost(post_data, token):
    """Create or update a post on Ghost via Admin API."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
        "Accept-Version": "v5.0",
    })
    
    # Check if post already exists by slug
    check_url = f"{GHOST_URL}/ghost/api/admin/posts/slug/{post_data['slug']}/"
    resp = session.get(check_url)
    
    payload = {
        "posts": [{
            "title": post_data["title"],
            "slug": post_data["slug"],
            "html": post_data["html"],
            "status": "published",
            "published_at": post_data["date"] if post_data["date"] else None,
            "tags": [{"name": t} for t in post_data["tags"]],
        }]
    }
    
    if resp.status_code == 200:
        # Update existing post
        existing = resp.json()["posts"][0]
        post_id = existing["id"]
        url = f"{GHOST_URL}/ghost/api/admin/posts/{post_id}/"
        resp = session.put(url, json=payload)
        action = "更新"
    else:
        # Create new post
        url = f"{GHOST_URL}/ghost/api/admin/posts/"
        resp = session.post(url, json=payload)
        action = "创建"
    
    if resp.status_code in (200, 201):
        print(f"✅ {action}成功: {post_data['title']}")
        return True
    else:
        print(f"❌ {action}失败: {post_data['title']}")
        print(f"   状态码: {resp.status_code}")
        print(f"   响应: {resp.text[:200]}")
        return False


def main():
    posts_dir = Path(HEXO_POSTS_DIR)
    if not posts_dir.exists():
        print(f"❌ 目录不存在: {posts_dir}")
        sys.exit(1)
    
    md_files = sorted(posts_dir.glob("*.md"))
    if not md_files:
        print(f"❌ 没有找到 Markdown 文件: {posts_dir}")
        sys.exit(1)
    
    print(f"🔍 找到 {len(md_files)} 篇文章")
    print(f"🏠 Ghost: {GHOST_URL}")
    
    token = generate_jwt_token()
    
    success = 0
    for f in md_files:
        post_data = parse_hexo_post(f)
        if post_to_ghost(post_data, token):
            success += 1
    
    print(f"\n📊 同步完成: {success}/{len(md_files)} 成功")


if __name__ == "__main__":
    main()
