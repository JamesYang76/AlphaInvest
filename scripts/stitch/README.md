# Stitch 화면 HTML / 이미지 받기

프로젝트 **18060349298714933034**, 화면 **AlphaInvest Integrated Dashboard** (`6f5b4585ca354f8fa7137146b411e7d5`) 기준입니다.

## 1) API 키

[Stitch](https://stitch.withgoogle.com)에서 발급한 키를 **프로젝트 루트의 `.env`** 에 넣습니다:

```env
STITCH_API_KEY=발급받은_키
```

(`.env`는 gitignore 되어 커밋되지 않습니다.)

## 2) 스크립트 실행

```bash
cd scripts/stitch
npm install
node fetch_screen.mjs
```

`fetch_screen.mjs`가 저장소 루트의 `.env`를 자동으로 읽습니다. 터미널에서만 쓰려면 `export STITCH_API_KEY=...` 도 동일하게 동작합니다.

결과는 저장소 루트의 **`stitch_assets/`** 에 저장됩니다.

- `alphainvest-integrated-dashboard.html`
- `alphainvest-integrated-dashboard.<png|jpg|…>`

## 3) `curl`만 쓰는 방법

스크립트가 출력하는 **HTML URL**과 **Image URL**을 복사한 뒤:

```bash
curl -L -o stitch_assets/dashboard.html "PASTE_HTML_URL"
curl -L -o stitch_assets/dashboard.png "PASTE_IMAGE_URL"
```

## 4) MCP (`@_davideast/stitch-mcp`)로 URL만 얻기

인증이 된 터미널에서:

```bash
npx @_davideast/stitch-mcp tool get_screen_code -d '{"projectId":"18060349298714933034","screenId":"6f5b4585ca354f8fa7137146b411e7d5"}'
```

응답에 호스팅 URL이 있으면 위와 같이 `curl -L`로 저장합니다.
