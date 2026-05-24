#!/usr/bin/env python3
"""YouTube Video Uploader — uploads a video to YouTube using OAuth 2.0.

This tool reads shared credentials (Client ID, Client Secret) from youtube_account.json
and video metadata from video_uploader.json.
On the first run, it launches a local browser for authorization and saves the token to
youtube_token.json. Subsequent runs use the token to upload videos headlessly.

Requires: pip install google-api-python-client google-auth-oauthlib requests
"""
import os, json, sys, time

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "video_uploader.json")
ACCOUNT_PATH = os.path.join(HERE, "youtube_account.json")
TOKEN_PATH = os.path.join(HERE, "youtube_token.json")

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 파일을 읽을 수 없습니다: {path}\n{e}")
        sys.exit(1)

def _shared(cfg, acct, key, default=""):
    v = cfg.get(key)
    if v not in (None, "", []):
        return v
    v = acct.get(key)
    if v not in (None, "", []):
        return v
    return default

def check_dependencies():
    missing = []
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        missing.append("google-api-python-client")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        missing.append("google-auth-oauthlib")
    try:
        import requests
    except ImportError:
        missing.append("requests")

    if missing:
        print("❌ 필요한 파이썬 라이브러리가 설치되지 않았습니다.")
        print(f"   설치 명령어: pip install {' '.join(missing)}")
        sys.exit(1)

def get_authenticated_service(client_id, client_secret):
    import pickle
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    creds = None

    if os.path.exists(TOKEN_PATH):
        try:
            with open(TOKEN_PATH, 'rb') as token_file:
                creds = pickle.load(token_file)
        except Exception as e:
            print(f"⚠️  기존 토큰 로드 실패 (다시 인증함): {e}")

    # 구글 OAuth 인증 클라이언트 구성 동적 제작
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost:5814/yt-oauth-callback", "http://127.0.0.1:5814/yt-oauth-callback"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 액세스 토큰 만료됨. 갱신 토큰(Refresh Token)으로 백그라운드 자동 갱신 중...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"❌ 토큰 자동 갱신 실패. 1회 재인증이 필요합니다: {e}")
                creds = None
        
        if not creds:
            print("\n🔐 [최초 1회 웹 브라우저 인증 시작] 🔐")
            print("👉 브라우저 창이 열리면 사장님의 유튜브 채널 구글 계정으로 로그인해 주십시오.")
            print("⚠️  '경고: 안전하지 않은 앱' 메시지가 뜨면 [고급] ➔ [임시 프로젝트(이동)]를 클릭하시면 됩니다.")
            try:
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                # 5814 포트 바인딩으로 사용자 대기 브라우저 실행
                creds = flow.run_local_server(port=5814, prompt='consent')
            except Exception as e:
                print(f"❌ OAuth 인증 실패: {e}")
                sys.exit(1)

        # 갱신된 토큰 저장
        try:
            with open(TOKEN_PATH, 'wb') as token_file:
                pickle.dump(creds, token_file)
            print("💾 자동 갱신 토큰을 youtube_token.json 파일에 안전하게 저장했습니다.")
        except Exception as e:
            print(f"⚠️  토큰 파일 저장 실패: {e}")

    return build('youtube', 'v3', credentials=creds)

def send_telegram_notification(acct, video_id, title):
    import requests
    tg_bot = (acct.get('TELEGRAM_BOT_TOKEN') or '').strip()
    tg_chat = (acct.get('TELEGRAM_CHAT_ID') or '').strip()
    if not (tg_bot and tg_chat):
        # 비서 config.md에서 조회용 시도
        try:
            sec_path = os.path.join(HERE, "..", "..", "secretary", "config.md")
            if os.path.exists(sec_path):
                with open(sec_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in lines:
                    if "TELEGRAM_BOT_TOKEN" in line:
                        tg_bot = line.split(":")[-1].strip()
                    elif "TELEGRAM_CHAT_ID" in line:
                        tg_chat = line.split(":")[-1].strip()
        except Exception:
            pass

    if tg_bot and tg_chat:
        msg = f"📺 [유튜브 업로드 완료]\n\n제목: {title}\n동영상 링크: https://youtu.be/{video_id}\n\n성공적으로 유튜브 채널에 영상이 등록되었습니다. 😊"
        try:
            requests.post(
                f"https://api.telegram.org/bot{tg_bot}/sendMessage",
                json={"chat_id": int(tg_chat), "text": msg},
                timeout=10
            )
            print("🔔 텔레그램으로 성과 전송 완료!")
        except Exception as e:
            print(f"⚠️  텔레그램 전송 실패: {e}")

def main():
    check_dependencies()

    if not os.path.exists(CONFIG_PATH):
        # 템플릿 생성
        default_config = {
            "VIDEO_FILE_PATH": "00_Raw/videos/test.mp4",
            "TITLE": "[브레이킹라이프] 지친 오늘 하루도 정말 수고 많았습니다",
            "DESCRIPTION": "오늘 하루 수고한 당신에게 건네는 따뜻한 한마디. #브레이킹라이프 #힐링 #직장인",
            "TAGS": ["브레이킹라이프", "힐링", "직장인", "스트레스해소"],
            "PRIVACY_STATUS": "unlisted",
            "CATEGORY_ID": "22"
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        print(f"📝 기본 설정 템플릿 생성 완료: {CONFIG_PATH}")
        print("   여기에 동영상 경로와 메타데이터를 수정하고 다시 시작해 주십시오.")
        sys.exit(0)

    cfg = load_json(CONFIG_PATH)
    acct = load_json(ACCOUNT_PATH) if os.path.exists(ACCOUNT_PATH) else {}

    client_id = (_shared(cfg, acct, "YOUTUBE_OAUTH_CLIENT_ID") or "").strip()
    client_secret = (_shared(cfg, acct, "YOUTUBE_OAUTH_CLIENT_SECRET") or "").strip()

    if not (client_id and client_secret):
        print("❌ YouTube OAuth 2.0 클라이언트 인증 정보가 비어있습니다.")
        print("   유튜브 대시보드 ⚙️ 설정에서 YOUTUBE_OAUTH_CLIENT_ID와 YOUTUBE_OAUTH_CLIENT_SECRET를 입력하세요.")
        print("   상세 가이드: video_uploader.md 파일을 참조하십시오.")
        sys.exit(1)

    video_file = cfg.get("VIDEO_FILE_PATH", "").strip()
    # 상대 경로인 경우 brain root/workspace root에서 찾도록 보정
    # tools/ -> youtube/ -> _agents/ -> brain root
    root_dir = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
    full_video_path = os.path.abspath(video_file) if os.path.isabs(video_file) else os.path.abspath(os.path.join(root_dir, video_file))

    if not os.path.exists(full_video_path):
        print(f"❌ 업로드할 동영상 파일을 찾을 수 없습니다: {full_video_path}")
        print("   video_uploader.json에서 동영상 파일 경로를 정확히 수정해 주십시오.")
        sys.exit(1)

    title = cfg.get("TITLE", "[브레이킹라이프] 신규 에피소드")
    description = cfg.get("DESCRIPTION", "")
    tags = cfg.get("TAGS", [])
    privacy_status = cfg.get("PRIVACY_STATUS", "unlisted")
    category_id = cfg.get("CATEGORY_ID", "22")  # People & Blogs

    print(f"\n📡 [유튜브 업로드 시작] 📡")
    print(f"🎬 동영상 파일: {full_video_path}")
    print(f"🏷️  제목        : {title}")
    print(f"🔐 공개 상태   : {privacy_status}")

    youtube = get_authenticated_service(client_id, client_secret)

    from googleapiclient.http import MediaFileUpload

    try:
        media = MediaFileUpload(full_video_path, chunksize=1024*1024, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": category_id
                },
                "status": {
                    "privacyStatus": privacy_status
                }
            },
            media_body=media
        )

        print("🚀 동영상 청크 데이터 스트리밍 전송 중...")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   📊 전송 진행률: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        print("\n🎉 [업로드 성공!] 🎉")
        print(f"🎥 동영상 ID  : {video_id}")
        print(f"🔗 동영상 링크: https://youtu.be/{video_id}")

        # 액티비티 로그 기록
        try:
            log_path = os.path.join(HERE, "..", "activity.log")
            now = time.strftime('%Y-%m-%d %H:%M:%S')
            with open(log_path, "a", encoding="utf-8") as log:
                log.write(f"[{now}] Uploader: uploaded '{title}' (ID: {video_id}, status: {privacy_status})\n")
        except Exception:
            pass

        # 텔레그램 전송
        send_telegram_notification(acct, video_id, title)

    except Exception as e:
        print(f"❌ 업로드 진행 중 치명적 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
