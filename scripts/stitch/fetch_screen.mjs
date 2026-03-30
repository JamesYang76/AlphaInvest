/**
 * Stitch 프로젝트/화면의 HTML·스크린샷 URL을 받아 stitch_assets/ 에 저장합니다.
 *
 * 필요: STITCH_API_KEY (stitch.withgoogle.com / GCP에서 발급)
 *
 * 사용:
 *   cd scripts/stitch && npm install
 *   프로젝트 루트 .env 에 STITCH_API_KEY=... 등록 후:
 *   node fetch_screen.mjs
   (또는 터미널에서 export STITCH_API_KEY=...)
 *
 * 선택 환경변수:
 *   STITCH_PROJECT_ID (기본: AlphaInvest 프로젝트)
 *   STITCH_SCREEN_ID (기본: AlphaInvest Integrated Dashboard)
 *   STITCH_OUT (출력 디렉터리, 기본: 저장소 루트의 stitch_assets/)
 */
import dotenv from "dotenv";
import { stitch } from "@google/stitch-sdk";
import { existsSync, readFileSync } from "fs";
import { mkdir, writeFile } from "fs/promises";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..", "..");
const ENV_PATH = join(REPO_ROOT, ".env");

/** 따옴표로 감싼 값·앞뒤 공백 정리 */
function stripQuotes(v) {
  if (!v || typeof v !== "string") return v;
  let s = v.trim();
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
    s = s.slice(1, -1);
  }
  return s.trim();
}

/**
 * dotenv가 다른 줄(하이픈 키, 파싱 오류 등) 때문에 실패해도 STITCH_API_KEY 한 줄은 직접 읽는다.
 */
function loadStitchKeyManual() {
  if (!existsSync(ENV_PATH)) return;
  let raw;
  try {
    raw = readFileSync(ENV_PATH, "utf8");
  } catch {
    return;
  }
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq < 0) continue;
    const key = trimmed.slice(0, eq).trim();
    if (key !== "STITCH_API_KEY") continue;
    const val = stripQuotes(trimmed.slice(eq + 1));
    if (val) {
      process.env.STITCH_API_KEY = val;
      return;
    }
  }
}

dotenv.config({ path: ENV_PATH });
loadStitchKeyManual();
if (process.env.STITCH_API_KEY) {
  process.env.STITCH_API_KEY = stripQuotes(process.env.STITCH_API_KEY);
}

const PROJECT_ID = process.env.STITCH_PROJECT_ID || "18060349298714933034";
const SCREEN_ID = process.env.STITCH_SCREEN_ID || "6f5b4585ca354f8fa7137146b411e7d5";
const OUT_DIR = process.env.STITCH_OUT || join(REPO_ROOT, "stitch_assets");
const BASE_NAME = "alphainvest-integrated-dashboard";

async function main() {
  if (!process.env.STITCH_API_KEY?.trim()) {
    console.error(
      "STITCH_API_KEY 가 없습니다. 프로젝트 루트 .env 에 STITCH_API_KEY=... 를 넣거나,\n" +
        "stitch.withgoogle.com 에서 발급한 뒤 export STITCH_API_KEY='...' 하고 실행하세요.\n" +
        "  node fetch_screen.mjs",
    );
    process.exit(1);
  }

  console.error("Fetching screen… project=%s screen=%s", PROJECT_ID, SCREEN_ID);
  const project = stitch.project(PROJECT_ID);
  const screen = await project.getScreen(SCREEN_ID);
  const htmlUrl = await screen.getHtml();
  const imageUrl = await screen.getImage();

  console.log("HTML URL:\n", htmlUrl);
  console.log("Image URL:\n", imageUrl);

  await mkdir(OUT_DIR, { recursive: true });

  const htmlRes = await fetch(htmlUrl);
  if (!htmlRes.ok) throw new Error(`HTML fetch failed: ${htmlRes.status}`);
  const htmlBody = Buffer.from(await htmlRes.arrayBuffer());
  const htmlPath = join(OUT_DIR, `${BASE_NAME}.html`);
  await writeFile(htmlPath, htmlBody);
  console.error("Wrote", htmlPath);

  const imgRes = await fetch(imageUrl);
  if (!imgRes.ok) throw new Error(`Image fetch failed: ${imgRes.status}`);
  const imgBody = Buffer.from(await imgRes.arrayBuffer());
  const ct = imgRes.headers.get("content-type") || "";
  const ext = ct.includes("png")
    ? "png"
    : ct.includes("webp")
      ? "webp"
      : ct.includes("jpeg") || ct.includes("jpg")
        ? "jpg"
        : imageUrl.includes(".png")
          ? "png"
          : "bin";
  const imgPath = join(OUT_DIR, `${BASE_NAME}.${ext}`);
  await writeFile(imgPath, imgBody);
  console.error("Wrote", imgPath);
  console.error("\nDone. You can also re-download with:\n  curl -L -o ...");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
