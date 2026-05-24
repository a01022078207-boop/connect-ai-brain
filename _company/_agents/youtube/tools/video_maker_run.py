#!/usr/bin/env python3
"""🎬 영상 제작 + 조합 원스탑 스크립트 (수정판)
- moviepy 1.x / 2.x 모두 지원
- imageio 폴백 지원  
- Gemini API 없어도 기본 스크립트로 동작
"""
import os, sys, json, subprocess, re, textwrap, random
from pathlib import Path
from datetime import datetime

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except: pass

HERE = Path(__file__).parent
OUTPUT_DIR = HERE / "_output"

# ── 설정 ──────────────────────────────────────────────────────────────────
TOPIC = "퇴근 후 지친 직장인을 위한 3가지 마음 위로법"
STYLE = "shorts"   # shorts = 768x1344, landscape = 1280x720
SLIDE_SEC = 4
WIDTH  = 768  if STYLE == "shorts" else 1280
HEIGHT = 1344 if STYLE == "shorts" else 720
GEMINI_KEY = "AIzaSyBoeyur1oyB6GlKc9MR-NK6QtpXnwucPWM"

# ── Gemini 스크립트 생성 (신규 API 엔드포인트) ────────────────────────────
def generate_script_gemini(topic, api_key):
    import urllib.request, urllib.error
    
    prompt = f"""당신은 브레이킹라이프(BreakingLife) 유튜브 채널 크리에이터입니다.
타깃: 20-40대 직장인, 지친 사회생활에 위로가 필요한 분들
다음 주제로 한국어 유튜브 쇼츠 스크립트 5장면을 작성하세요.

주제: {topic}

JSON만 반환 (다른 텍스트 없이):
{{"title":"[브레이킹라이프] 제목","description":"설명 #브레이킹라이프 #힐링","tags":["브레이킹라이프","힐링","직장인"],"scenes":[{{"narration":"따뜻한 2-3문장","caption":"자막 15자이내"}}]}}"""

    # gemini-2.0-flash 시도 → flash-lite 폴백
    for model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        body = json.dumps({"contents":[{"parts":[{"text":prompt}]}],
                           "generationConfig":{"temperature":0.8,"maxOutputTokens":1024}}).encode()
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = re.sub(r"```json\s*|\s*```","",text).strip()
            s = text.find("{"); e = text.rfind("}")+1
            return json.loads(text[s:e])
        except Exception as ex:
            print(f"  {model} 실패: {ex}")
    return None

# ── PIL 이미지 생성 ────────────────────────────────────────────────────────
def create_slide(caption, narration, index, total, w, h, out_path):
    from PIL import Image, ImageDraw, ImageFont
    
    palettes = [
        [(15,15,35),(55,25,75)],
        [(8,25,45),(25,70,90)],
        [(35,8,25),(95,25,55)],
        [(10,35,25),(25,80,60)],
        [(45,25,8),(115,65,15)],
    ]
    c1,c2 = palettes[index % len(palettes)]
    
    img = Image.new("RGB",(w,h),c1)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y/h
        r,g,b = [int(c1[i]+(c2[i]-c1[i])*t) for i in range(3)]
        draw.line([(0,y),(w,y)],fill=(r,g,b))
    
    # 별빛
    random.seed(index*77)
    for _ in range(100):
        sx,sy = random.randint(0,w), random.randint(0,h//2)
        sa = random.randint(60,200)
        draw.ellipse([sx-1,sy-1,sx+1,sy+1],fill=(255,255,255))
    
    # 진행 바
    draw.rectangle([30,h-30,w-30,h-24],fill=(80,80,80))
    pw = int((index+1)/total*(w-60))
    draw.rectangle([30,h-30,30+pw,h-24],fill=(255,195,90))
    
    # 폰트
    def getf(size):
        for f in ["malgunbd.ttf","malgun.ttf",
                  "C:/Windows/Fonts/malgunbd.ttf","C:/Windows/Fonts/malgun.ttf",
                  "gulim.ttc","C:/Windows/Fonts/gulim.ttc"]:
            try: return ImageFont.truetype(f,size)
            except: pass
        return ImageFont.load_default()
    
    # 상단 브랜드
    fb = getf(32)
    draw.text((w-180,25),"BreakingLife",font=fb,fill=(255,195,90))
    
    # 중앙 자막 (큰)
    fl = getf(70)
    lines = textwrap.wrap(caption, width=10)
    y0 = h//2 - len(lines)*45
    for ln in lines:
        bb = draw.textbbox((0,0),ln,font=fl)
        tw = bb[2]-bb[0]
        draw.text(((w-tw)//2+3,y0+3),ln,font=fl,fill=(0,0,0))
        draw.text(((w-tw)//2,y0),ln,font=fl,fill=(255,220,140))
        y0 += (bb[3]-bb[1])+12
    
    # 나레이션 (작게)
    fs = getf(38)
    nlines = textwrap.wrap(narration[:70],width=20)[:3]
    yn = h*3//4
    for ln in nlines:
        bb = draw.textbbox((0,0),ln,font=fs)
        tw = bb[2]-bb[0]
        draw.text(((w-tw)//2,yn),ln,font=fs,fill=(195,200,220))
        yn += (bb[3]-bb[1])+8
    
    img.save(str(out_path),"JPEG",quality=95)

# ── 영상 합성 ──────────────────────────────────────────────────────────────
def make_video(img_paths, out_path, slide_sec, w, h):
    # 1) FFmpeg
    import shutil
    if shutil.which("ffmpeg"):
        list_txt = out_path.parent / "_list.txt"
        with open(list_txt,"w",encoding="utf-8") as f:
            for p in img_paths:
                f.write(f"file '{str(p).replace(chr(92),'/') }'\nduration {slide_sec}\n")
            f.write(f"file '{str(img_paths[-1]).replace(chr(92),'/')}'\n")
        cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",str(list_txt),
               "-vf",f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,fps=24",
               "-c:v","libx264","-preset","fast","-crf","23","-pix_fmt","yuv420p",str(out_path)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        list_txt.unlink(missing_ok=True)
        if r.returncode == 0: return True,"ffmpeg"
        print(f"  ffmpeg stderr: {r.stderr[-300:]}")
    
    # 2) moviepy 2.x
    try:
        from moviepy import ImageClip, concatenate_videoclips
        clips = [ImageClip(str(p),duration=slide_sec) for p in img_paths]
        concatenate_videoclips(clips).write_videofile(str(out_path),fps=24,codec="libx264",logger=None)
        return True,"moviepy2"
    except Exception as e:
        print(f"  moviepy2 실패: {e}")
    
    # 3) moviepy 1.x
    try:
        from moviepy.editor import ImageClip, concatenate_videoclips
        clips = [ImageClip(str(p)).set_duration(slide_sec) for p in img_paths]
        concatenate_videoclips(clips,method="compose").write_videofile(str(out_path),fps=24,codec="libx264",logger=None)
        return True,"moviepy1"
    except Exception as e:
        print(f"  moviepy1 실패: {e}")
    
    # 4) imageio + imageio_ffmpeg
    try:
        import imageio, numpy as np
        from PIL import Image as PILImg
        writer = imageio.get_writer(str(out_path),fps=24,codec="libx264",quality=8)
        for p in img_paths:
            frame = np.array(PILImg.open(p).convert("RGB"))
            for _ in range(slide_sec*24):
                writer.append_data(frame)
        writer.close()
        return True,"imageio"
    except Exception as e:
        print(f"  imageio 실패: {e}")
    
    return False,"모든 방법 실패"

# ── SRT ────────────────────────────────────────────────────────────────────
def make_srt(scenes, slide_sec, srt_path):
    def t(s):
        return f"{int(s//3600):02}:{int((s%3600)//60):02}:{int(s%60):02},{int((s-int(s))*1000):03}"
    lines=[]
    for i,sc in enumerate(scenes):
        lines.append(f"{i+1}\n{t(i*slide_sec)} --> {t((i+1)*slide_sec)}\n{sc.get('caption','')}\n")
    srt_path.write_text("\n".join(lines),encoding="utf-8")

# ── 메인 ──────────────────────────────────────────────────────────────────
def main():
    print("🎬 AI 영상 자동 제작 — BreakingLife (수정판)")
    print("="*55)
    
    # Pillow 확인
    try:
        from PIL import Image
    except ImportError:
        subprocess.run([sys.executable,"-m","pip","install","Pillow","-q"])
    
    # 스크립트 생성
    print(f"\n📌 주제: {TOPIC}")
    print("\n🤖 Gemini AI 스크립트 생성 중...")
    script = generate_script_gemini(TOPIC, GEMINI_KEY)
    
    if script:
        print(f"  ✅ 완성: {script.get('title','')}")
    else:
        print("  ℹ️ 기본 템플릿 사용")
        script = {
            "title": "[브레이킹라이프] 퇴근 후 지친 당신을 위한 3가지 위로",
            "description": "퇴근 후 지쳐버린 당신에게. 오늘도 정말 수고 많았어요. 브레이킹라이프가 곁에 있을게요 🧡 #브레이킹라이프 #힐링 #직장인 #위로 #퇴근",
            "tags": ["브레이킹라이프","힐링","직장인","위로","퇴근","감성","쇼츠"],
            "scenes": [
                {"narration":"오늘도 하루 종일 정말 수고 많으셨습니다. 당신이 버텨온 하루가 얼마나 대단한지 알아요.","caption":"오늘도 수고했어요 🧡"},
                {"narration":"첫 번째 위로 — 잠깐 핸드폰 내려놓고 창문 밖을 바라보세요. 그 5분이 당신의 숨통을 틔워줄 거예요.","caption":"① 창밖을 보세요"},
                {"narration":"두 번째 위로 — 따뜻한 음료 한 잔. 커피든 차든, 그 온기가 손끝에서 마음까지 전해져요.","caption":"② 따뜻한 음료 한 잔"},
                {"narration":"세 번째 위로 — 오늘 힘들었던 일 딱 하나만 적어보세요. 쓰는 것만으로도 마음이 한결 가벼워져요.","caption":"③ 한 줄 일기"},
                {"narration":"내일도, 모레도 브레이킹라이프가 함께할게요. 구독 누르시면 매일 위로를 드릴게요 🧡","caption":"💙 구독하고 함께해요"},
            ]
        }
    
    scenes = script["scenes"]
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    title_safe = re.sub(r'[\\/:*?"<>|]','_',script["title"])[:45]
    out_mp4 = OUTPUT_DIR / f"{title_safe}_{ts}.mp4"
    out_srt = OUTPUT_DIR / f"{title_safe}_{ts}.srt"
    out_json = OUTPUT_DIR / f"{title_safe}_{ts}_script.json"
    tmp_dir = OUTPUT_DIR / f"_tmp_{ts}"
    OUTPUT_DIR.mkdir(exist_ok=True)
    tmp_dir.mkdir(exist_ok=True)
    
    # 이미지 생성
    print(f"\n🖼️  이미지 생성 중 ({len(scenes)}장, {WIDTH}×{HEIGHT})...")
    img_paths = []
    for i, sc in enumerate(scenes):
        p = tmp_dir / f"s{i:02d}.jpg"
        print(f"  [{i+1}/{len(scenes)}] {sc.get('caption','')[:25]}")
        create_slide(sc.get("caption",""), sc.get("narration",""), i, len(scenes), WIDTH, HEIGHT, p)
        img_paths.append(p)
    
    # 영상 합성
    print(f"\n🎞️  영상 합성 중...")
    ok, method = make_video(img_paths, out_mp4, SLIDE_SEC, WIDTH, HEIGHT)
    
    # SRT + JSON 저장
    make_srt(scenes, SLIDE_SEC, out_srt)
    out_json.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # video_uploader.json 자동 업데이트
    up_cfg_path = HERE / "video_uploader.json"
    if up_cfg_path.exists():
        up_cfg = json.loads(up_cfg_path.read_text(encoding="utf-8"))
    else:
        up_cfg = {}
    up_cfg.update({
        "VIDEO_FILE_PATH": str(out_mp4),
        "TITLE": script["title"],
        "DESCRIPTION": script.get("description",""),
        "TAGS": script.get("tags",[]),
        "PRIVACY_STATUS": "unlisted",
        "CATEGORY_ID": "22"
    })
    up_cfg_path.write_text(json.dumps(up_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # 결과
    print("\n" + "="*55)
    if ok:
        size = out_mp4.stat().st_size/1024/1024
        print(f"✅ 영상 완성! ({method}, {size:.1f}MB)")
        print(f"  📹 {out_mp4}")
        print(f"  📄 {out_srt}")
        print(f"  📝 {out_json}")
        print(f"\n📋 video_uploader.json 자동 업데이트 완료!")
        print(f"  제목: {script['title']}")
    else:
        print(f"⚠️  영상 합성 실패 — {method}")
        print(f"  이미지는 {tmp_dir} 에 있습니다.")
        print("  이미지를 수동으로 영상으로 변환하거나:")
        print("  FFmpeg 설치: https://ffmpeg.org/download.html → 윈도우 빌드 다운로드 → PATH 추가")
        return
    
    # 정리
    import shutil
    try: shutil.rmtree(tmp_dir)
    except: pass
    
    print("\n✨ 다음 단계: video_uploader.py 실행으로 YouTube 업로드!")

if __name__ == "__main__":
    main()
