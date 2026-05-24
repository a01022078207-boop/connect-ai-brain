#!/usr/bin/env python3
"""🎬 AI 영상 자동 제작 — BreakingLife 전용

주제 입력 → Gemini AI 스크립트 생성 → 이미지 생성 → MP4 영상 조합 → 자막 생성
완성된 영상은 _output/ 폴더에 저장됩니다.
"""
import os, sys, json, subprocess, re, textwrap, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "video_maker.json"
SHARED_CONFIG_PATH = HERE / "youtube_account.json"
OUTPUT_DIR = HERE / "_output"

# ── 설정 로딩 ──────────────────────────────────────────────────────────────
def load_config():
    cfg = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    if SHARED_CONFIG_PATH.exists():
        with open(SHARED_CONFIG_PATH, "r", encoding="utf-8") as f:
            shared = json.load(f)
        for k in ("GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "OLLAMA_URL", "MODEL"):
            if k in shared and not cfg.get(k):
                cfg[k] = shared[k]
    return cfg

# ── 패키지 자동 설치 ───────────────────────────────────────────────────────
def ensure_package(pkg_import, pip_name=None):
    try:
        __import__(pkg_import)
        return True
    except ImportError:
        print(f"📦 {pip_name or pkg_import} 자동 설치 중...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", pip_name or pkg_import, "-q"],
                               capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ⚠️ 설치 실패: {result.stderr[-200:]}")
            return False
        return True

# ── Gemini AI 스크립트 생성 ────────────────────────────────────────────────
def generate_script_gemini(topic, style, language, api_key, num_scenes=5):
    import urllib.request, urllib.error
    lang_label = "한국어" if language == "ko" else "English"
    aspect = "세로형 9:16 (쇼츠/릴스)" if style == "shorts" else "가로형 16:9"
    
    prompt = f"""당신은 유튜브 크리에이터입니다. 다음 주제로 {lang_label} {aspect} 유튜브 영상 스크립트를 작성하세요.
브랜드명: 브레이킹라이프 (20-40대 직장인/사회생활 지친 분들을 위한 힐링 콘텐츠)
주제: {topic}
장면 수: {num_scenes}개

반드시 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "title": "영상 제목 (클릭하고 싶은 제목, 브레이킹라이프 스타일)",
  "description": "유튜브 설명란 (300자 이내, 해시태그 포함, #브레이킹라이프 필수)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5", "브레이킹라이프", "힐링"],
  "scenes": [
    {{
      "narration": "나레이션 텍스트 (2~3문장, 따뜻하고 공감 가는 어조)",
      "image_prompt": "영어 이미지 생성 프롬프트 (cinematic, warm, emotional style)",
      "caption": "화면에 표시할 자막 (20자 이내)"
    }}
  ]
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 2048}
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    text = re.sub(r"```json\s*|\s*```", "", text).strip()
    # JSON 시작/끝 위치 찾기
    start = text.find('{')
    end = text.rfind('}') + 1
    if start >= 0 and end > start:
        text = text[start:end]
    return json.loads(text)

# ── 텍스트 이미지 생성 (PIL로 감성 배경 생성) ─────────────────────────────
def create_text_image(caption, narration, index, total, width, height, output_path):
    """PIL로 감성적인 텍스트 슬라이드 이미지 생성"""
    from PIL import Image, ImageDraw, ImageFont
    import math
    
    # 감성 색상 팔레트 (브레이킹라이프 스타일)
    palettes = [
        [(20, 20, 40), (60, 30, 80)],       # 밤하늘 보라
        [(10, 30, 50), (30, 80, 100)],       # 새벽 바다
        [(40, 10, 30), (100, 30, 60)],       # 와인빛 노을
        [(15, 40, 30), (30, 90, 70)],        # 숲속 초록
        [(50, 30, 10), (120, 70, 20)],       # 황혼 황금
    ]
    c1, c2 = palettes[index % len(palettes)]
    
    img = Image.new("RGB", (width, height), c1)
    draw = ImageDraw.Draw(img)
    
    # 그라데이션 배경
    for y in range(height):
        ratio = y / height
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # 별빛 효과
    import random
    random.seed(index * 42)
    for _ in range(80):
        sx = random.randint(0, width)
        sy = random.randint(0, height // 2)
        sa = random.randint(80, 220)
        sr = random.randint(1, 3)
        draw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=(255, 255, 255, sa))
    
    # 진행 표시 (하단 바)
    bar_h = 6
    bar_y = height - bar_h - 20
    draw.rectangle([20, bar_y, width-20, bar_y+bar_h], fill=(255,255,255,30))
    progress = int((index + 1) / total * (width - 40))
    draw.rectangle([20, bar_y, 20+progress, bar_y+bar_h], fill=(255,200,100))
    
    # 폰트 로드 시도
    def get_font(size):
        # Windows 한글 폰트 시도
        font_candidates = [
            "malgunbd.ttf", "malgun.ttf",  # 맑은 고딕 Bold/Regular
            "NanumGothicBold.ttf", "NanumGothic.ttf",
            "gulim.ttc", "batang.ttc",
            "C:/Windows/Fonts/malgunbd.ttf",
            "C:/Windows/Fonts/malgun.ttf",
        ]
        for fc in font_candidates:
            try:
                return ImageFont.truetype(fc, size)
            except:
                pass
        return ImageFont.load_default()
    
    # 메인 자막 (큰 글씨)
    caption_lines = textwrap.wrap(caption, width=12)
    font_big = get_font(72 if style == "shorts" else 60)
    y_pos = height // 2 - 80
    for line in caption_lines:
        bbox = draw.textbbox((0,0), line, font=font_big)
        tw = bbox[2] - bbox[0]
        # 텍스트 그림자
        draw.text(((width-tw)//2 + 3, y_pos + 3), line, font=font_big, fill=(0,0,0,180))
        draw.text(((width-tw)//2, y_pos), line, font=font_big, fill=(255, 220, 150))
        y_pos += (bbox[3] - bbox[1]) + 15
    
    # 나레이션 (작은 글씨)
    narr_lines = textwrap.wrap(narration[:80] + ("..." if len(narration) > 80 else ""), width=22)
    font_small = get_font(36 if style == "shorts" else 30)
    y_pos_narr = height * 3 // 4
    for line in narr_lines[:3]:
        bbox = draw.textbbox((0,0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text(((width-tw)//2, y_pos_narr), line, font=font_small, fill=(200, 200, 220))
        y_pos_narr += (bbox[3] - bbox[1]) + 10
    
    # 브랜드 워터마크
    font_brand = get_font(28)
    brand_text = "BreakingLife"
    bbox = draw.textbbox((0,0), brand_text, font=font_brand)
    bw = bbox[2] - bbox[0]
    draw.text((width - bw - 20, 20), brand_text, font=font_brand, fill=(255, 200, 100, 150))
    
    img.save(output_path, "JPEG", quality=95)
    return output_path

# ── FFmpeg로 이미지→영상 합성 ─────────────────────────────────────────────
def images_to_video_ffmpeg(image_paths, output_path, slide_duration=4, fps=24):
    import shutil
    if not shutil.which("ffmpeg"):
        return False, "FFmpeg 미설치"
    
    list_file = output_path.parent / "_ffmpeg_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in image_paths:
            f.write(f"file '{str(p).replace(chr(92), '/')}'\nduration {slide_duration}\n")
        # 마지막 프레임 한 번 더 (FFmpeg concat 요구사항)
        if image_paths:
            f.write(f"file '{str(image_paths[-1]).replace(chr(92), '/')}'\n")
    
    w, h = (768, 1344) if style == "shorts" else (1280, 720)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,fps={fps}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    list_file.unlink(missing_ok=True)
    if result.returncode != 0:
        return False, result.stderr[-500:]
    return True, ""

# ── MoviePy로 이미지→영상 합성 ────────────────────────────────────────────
def images_to_video_moviepy(image_paths, output_path, slide_duration=4):
    try:
        from moviepy.editor import ImageClip, concatenate_videoclips
        clips = [ImageClip(str(p)).set_duration(slide_duration) for p in image_paths]
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(str(output_path), fps=24, codec="libx264", logger=None)
        return True, ""
    except Exception as e:
        return False, str(e)

# ── SRT 자막 생성 ─────────────────────────────────────────────────────────
def make_srt(scenes, slide_duration, output_path):
    def fmt_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    lines = []
    for i, scene in enumerate(scenes):
        start = i * slide_duration
        end = start + slide_duration
        lines.append(f"{i+1}\n{fmt_time(start)} --> {fmt_time(end)}\n{scene.get('caption','')}\n")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ── 글로벌 변수 ───────────────────────────────────────────────────────────
style = "shorts"

# ── 메인 ──────────────────────────────────────────────────────────────────
def main():
    global style
    print("🎬 AI 영상 자동 제작 시작 — BreakingLife")
    print("=" * 55)

    cfg = load_config()
    gemini_key = (cfg.get("GEMINI_API_KEY") or "").strip()
    ollama_url = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").strip()
    ollama_model = (cfg.get("MODEL") or "").strip()
    topic = (cfg.get("VIDEO_TOPIC") or "").strip()
    style = (cfg.get("VIDEO_STYLE") or "shorts").strip()
    language = (cfg.get("LANGUAGE") or "ko").strip()
    slide_sec = int(cfg.get("SLIDE_DURATION_SEC") or 4)
    tg_token = (cfg.get("TELEGRAM_BOT_TOKEN") or "").strip()
    tg_chat = (cfg.get("TELEGRAM_CHAT_ID") or "").strip()

    if not topic:
        print("⚠️  VIDEO_TOPIC이 비어있습니다.")
        print("   video_maker.json 파일에서 VIDEO_TOPIC을 설정해주세요.")
        sys.exit(1)

    print(f"📌 주제: {topic}")
    print(f"📐 스타일: {style} | 언어: {language} | 장면당 {slide_sec}초")

    # ── 스크립트 생성
    print("\n🤖 AI 스크립트 생성 중...")
    script = None
    if gemini_key:
        try:
            script = generate_script_gemini(topic, style, language, gemini_key)
            print(f"  ✅ Gemini AI 스크립트 완성!")
            print(f"  제목: {script['title']}")
        except Exception as e:
            print(f"  ⚠️ Gemini 오류: {e}")

    if not script:
        print("  ℹ️ 기본 템플릿 스크립트 사용")
        script = {
            "title": f"[브레이킹라이프] {topic}",
            "description": f"{topic} | 지친 당신에게 전하는 브레이킹라이프의 이야기 #브레이킹라이프 #힐링 #직장인 #위로",
            "tags": ["브레이킹라이프", "힐링", "직장인", "위로", "감성", topic],
            "scenes": [
                {"narration": f"오늘도 하루 종일 수고 많으셨습니다.", "image_prompt": f"peaceful night city view, warm lights, emotional", "caption": f"오늘도 수고했어요 💙"},
                {"narration": f"{topic}에 대해 함께 이야기해 봐요.", "image_prompt": f"cozy cafe window, rainy day, warm atmosphere", "caption": f"잠깐, 여기 봐요"},
                {"narration": "힘든 하루를 보내고 있다면, 당신만 그런 게 아니에요.", "image_prompt": "person sitting alone, soft light, hopeful", "caption": "혼자가 아니에요"},
                {"narration": "작은 위로가 큰 힘이 된다는 걸 기억해주세요.", "image_prompt": "sunrise over mountains, golden light, new beginning", "caption": "내일은 더 좋을 거예요"},
                {"narration": "브레이킹라이프와 함께라면 괜찮아요. 구독 눌러주세요!", "image_prompt": "hands holding heart, warm golden light, love", "caption": "👍 구독·좋아요!"},
            ]
        }

    scenes = script.get("scenes", [])
    title_safe = re.sub(r'[\\/:*?"<>|]', '_', script['title'])[:50]
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    OUTPUT_DIR.mkdir(exist_ok=True)
    tmp_dir = OUTPUT_DIR / f"_tmp_{date_str}"
    tmp_dir.mkdir(exist_ok=True)

    output_video = OUTPUT_DIR / f"{title_safe}_{date_str}.mp4"
    output_srt   = OUTPUT_DIR / f"{title_safe}_{date_str}.srt"

    # ── Pillow 설치 확인
    if not ensure_package("PIL", "Pillow"):
        print("❌ Pillow 설치 실패. 이미지 생성 불가.")
        sys.exit(1)

    # ── 이미지 생성
    w = 768 if style == "shorts" else 1280
    h = 1344 if style == "shorts" else 720
    print(f"\n🖼️  이미지 생성 중 ({len(scenes)}장, {w}×{h})...")

    img_paths = []
    for i, scene in enumerate(scenes):
        img_path = tmp_dir / f"scene_{i:02d}.jpg"
        print(f"  [{i+1}/{len(scenes)}] {scene.get('caption', '')[:25]}")
        try:
            create_text_image(
                scene.get("caption", ""), 
                scene.get("narration", ""),
                i, len(scenes), w, h, img_path
            )
            img_paths.append(img_path)
        except Exception as e:
            print(f"    ❌ 이미지 생성 오류: {e}")
            import traceback; traceback.print_exc()

    if not img_paths:
        print("❌ 이미지 생성 실패")
        sys.exit(1)

    # ── 영상 합성
    print(f"\n🎞️  영상 합성 중... ({len(img_paths)}장 × {slide_sec}초 = {len(img_paths)*slide_sec}초)")
    ok = False
    err = ""
    
    # FFmpeg 먼저 시도
    import shutil
    if shutil.which("ffmpeg"):
        print("  🔧 FFmpeg로 합성 중...")
        ok, err = images_to_video_ffmpeg(img_paths, output_video, slide_sec)
        if ok:
            print("  ✅ FFmpeg 합성 성공")
    
    if not ok:
        print(f"  ⚠️ FFmpeg 시도 실패: {err[:100]}")
        # MoviePy 폴백
        if ensure_package("moviepy", "moviepy"):
            print("  🔧 MoviePy로 합성 중...")
            ok, err = images_to_video_moviepy(img_paths, output_video, slide_sec)
            if ok:
                print("  ✅ MoviePy 합성 성공")
            else:
                print(f"  ❌ MoviePy도 실패: {err[:200]}")

    # ── SRT 생성
    make_srt(scenes, slide_sec, output_srt)

    # ── 스크립트 JSON 저장
    script_json_path = OUTPUT_DIR / f"{title_safe}_{date_str}_script.json"
    with open(script_json_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    
    # video_uploader.json 자동 업데이트
    uploader_cfg = {}
    uploader_cfg_path = HERE / "video_uploader.json"
    if uploader_cfg_path.exists():
        with open(uploader_cfg_path, "r", encoding="utf-8") as f:
            uploader_cfg = json.load(f)
    uploader_cfg["VIDEO_FILE_PATH"] = str(output_video)
    uploader_cfg["TITLE"] = script["title"]
    uploader_cfg["DESCRIPTION"] = script.get("description", "")
    uploader_cfg["TAGS"] = script.get("tags", [])
    with open(uploader_cfg_path, "w", encoding="utf-8") as f:
        json.dump(uploader_cfg, f, ensure_ascii=False, indent=2)

    # ── 결과 출력
    print("\n" + "=" * 55)
    if ok:
        size_mb = output_video.stat().st_size / 1024 / 1024 if output_video.exists() else 0
        print(f"✅ 영상 완성! ({size_mb:.1f} MB)")
        print(f"  📹 영상: {output_video}")
        print(f"  📄 자막: {output_srt}")
        print(f"  📝 스크립트: {script_json_path}")
        print(f"\n📋 YouTube 업로드 준비 완료:")
        print(f"  제목: {script['title']}")
        print(f"  태그: {', '.join(script.get('tags', [])[:5])}")
        print(f"\n💡 video_uploader.py 실행하면 YouTube에 자동 업로드됩니다!")
        
        if tg_token and tg_chat:
            try:
                import urllib.request
                msg = f"🎬 *AI 영상 제작 완료!*\n제목: {script['title']}\n파일: {output_video.name}\n크기: {size_mb:.1f}MB"
                data = json.dumps({"chat_id": tg_chat, "text": msg, "parse_mode": "Markdown"}).encode()
                req = urllib.request.Request(f"https://api.telegram.org/bot{tg_token}/sendMessage",
                                            data=data, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=10)
                print("  📱 텔레그램 알림 완료")
            except Exception as e:
                print(f"  텔레그램 실패: {e}")
    else:
        print("⚠️  영상 합성 실패.")
        print(f"  이미지 {len(img_paths)}장은 {tmp_dir}에 저장되었습니다.")
        print(f"  FFmpeg 설치: https://ffmpeg.org/download.html")
    
    # 임시 파일 정리
    try:
        import shutil as sh
        sh.rmtree(tmp_dir)
    except:
        pass

if __name__ == "__main__":
    main()
