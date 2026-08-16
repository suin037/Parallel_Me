import { useCallback, useEffect, useRef, useState } from "react";
import Avatar from "./Avatar.jsx";
import {
  BEARD,
  BROW_SHAPE_ITEMS,
  BROW_THICKNESS,
  CLOTHES,
  CLOTHES_COLORS,
  EYES,
  GLASSES_OPTIONS,
  HAIR_COLORS,
  HAIR_STYLES,
  MOUTH,
  SKIN_COLORS,
} from "../data/avatarOptions.js";

// 카메라로 얼굴을 한 장 찍어 아바타 설정의 '시작점'을 잡는다.
//
// 닮게 만드는 기능이 아니다. 선택지가 5만 조합뿐이라 대부분의 실제 얼굴은 이 안에 없다.
// 그래서 결과를 바로 덮어쓰지 않고 반드시 확인 단계를 거친다 — 사진과 결과를 나란히
// 보여주고, 무엇이 바뀌는지 알려준 뒤, 사용자가 적용/취소를 고른다.
//
// 사진 취급: 프레임은 메모리(state)에만 있고 적용·취소 어느 쪽이든 즉시 버린다.
// 파일이나 localStorage 에 쓰지 않는다. 다만 분석은 서버를 거치므로 기기 밖으로 전송된다.

// 얼굴형은 buildOptions 에서 뺐다 — 되살리면 여기도 같이 되살릴 것.
const FIELD_LABELS = {
  hairStyle: "헤어스타일",
  hairColor: "헤어 컬러",
  skinColor: "피부색",
  eyes: "눈",
  lashes: "속눈썹",
  eyebrows: "눈썹 모양",
  browThickness: "눈썹 굵기",
  mouth: "표정",
  glasses: "안경",
  beard: "수염",
  clothes: "의상",
  clothesColor: "의상 컬러",
  pattern: "옷 무늬",
};

// 백엔드가 고를 수 있는 값 목록. avatarOptions.js 가 원본이라 여기서 파생시킨다.
// 새 헤어스타일을 추가하면 자동으로 후보에 포함된다.
function buildOptions() {
  const ids = (arr) => arr.map((x) => x.id);
  const labels = (arr) => Object.fromEntries(arr.map((x) => [x.id, x.label]));
  return {
    // id 만 보내면 모델이 'pointedShort' 가 무슨 모양인지 알 수가 없어 무난한 값으로
    // 몰린다. 뜻을 같이 보낸다. 헤어는 이름만으로도 부족해서(우리 '언더컷'은 올백
    // 계열인데 이름만 보면 투블럭으로 읽힌다) 그려진 모양 설명까지 붙인다.
    labels: {
      hairStyle: Object.fromEntries(
        HAIR_STYLES.map((h) => [h.id, h.desc ? `${h.label} (${h.desc})` : h.label])
      ),
      eyes: labels(EYES),
      eyebrows: labels(BROW_SHAPE_ITEMS),
      browThickness: labels(BROW_THICKNESS),
      mouth: labels(MOUTH),
      glasses: labels(GLASSES_OPTIONS),
      beard: labels(BEARD),
      clothes: labels(CLOTHES),
    },
    // 얼굴형은 일부러 뺐다. 목록에 없으면 모델이 값을 못 내고, 그러면 사용자가
    // 직접 고른 얼굴형이 그대로 남는다.
    //
    // 왜 뺐나: 우리 아바타를 얼굴형만 바꿔 5장 만들어 그대로 넣었더니 1/5 만 맞혔다.
    // 사진 노이즈도 없고 우리가 그린 그림인데 네모형을 계란형이라고 했다. 5종의
    // 차이가 턱 부근 15~30px 뿐이라 640px 로 줄이면 판별이 안 된다. 실사진 10장에서도
    // 9~10장이 계란형 하나로 몰렸고, 프롬프트에 판단 기준을 넣어도 1칸만 움직였다.
    // 그대로 두면 '못 맞히는' 게 아니라 '사용자가 고른 얼굴형을 계란형으로 덮는' 것이라
    // 안 건드리는 편이 낫다. 얼굴형을 더 뚜렷하게 다시 그리면 그때 되살리면 된다.
    hairStyle: ids(HAIR_STYLES),
    eyes: ids(EYES),
    eyebrows: ids(BROW_SHAPE_ITEMS),
    browThickness: ids(BROW_THICKNESS),
    mouth: ids(MOUTH),
    glasses: ids(GLASSES_OPTIONS),
    beard: [...ids(BEARD), null], // null = 수염 없음
    clothes: ids(CLOTHES),
    skinColor: SKIN_COLORS,
    hairColor: HAIR_COLORS,
    clothesColor: CLOTHES_COLORS,
  };
}

export default function AvatarFromPhoto({ current, onResult, onClose }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const cameraRequestRef = useRef(0);
  const [status, setStatus] = useState("starting"); // starting | ready | working | review | error
  const [error, setError] = useState(null);
  const [shot, setShot] = useState(null); // 찍은 프레임 (메모리에만)
  const [result, setResult] = useState(null); // 모델이 고른 설정

  const stopCamera = useCallback(() => {
    cameraRequestRef.current += 1; // 진행 중인 getUserMedia 응답도 무효화한다.
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const startCamera = useCallback(async () => {
    setError(null);
    setStatus("starting");
    const requestId = cameraRequestRef.current + 1;
    cameraRequestRef.current = requestId;
    try {
      if (!window.isSecureContext) {
        throw new Error("카메라는 HTTPS 또는 localhost 주소에서만 사용할 수 있습니다.");
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("이 브라우저에서는 카메라 기능을 사용할 수 없습니다.");
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 640 } },
        audio: false,
      });
      // 개발 모드 StrictMode 재실행이나 닫기 이후 늦게 도착한 스트림은 즉시 폐기한다.
      if (cameraRequestRef.current !== requestId) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) throw new Error("카메라 화면을 준비하지 못했습니다.");
      video.srcObject = stream;

      // getUserMedia 성공 직후에도 videoWidth/Height가 한동안 0일 수 있다.
      // 이때 촬영하면 검은 프레임이 분석 서버로 가므로 실제 프레임을 기다린다.
      await new Promise((resolve, reject) => {
        if (video.readyState >= HTMLMediaElement.HAVE_METADATA && video.videoWidth > 0) {
          resolve();
          return;
        }
        const timeout = window.setTimeout(() => {
          cleanup();
          reject(new Error("카메라 영상 준비 시간이 초과되었습니다."));
        }, 8000);
        const ready = () => {
          if (!video.videoWidth || !video.videoHeight) return;
          cleanup();
          resolve();
        };
        const failed = () => {
          cleanup();
          reject(new Error("카메라 영상을 재생하지 못했습니다."));
        };
        const cleanup = () => {
          window.clearTimeout(timeout);
          video.removeEventListener("loadedmetadata", ready);
          video.removeEventListener("canplay", ready);
          video.removeEventListener("error", failed);
        };
        video.addEventListener("loadedmetadata", ready);
        video.addEventListener("canplay", ready);
        video.addEventListener("error", failed);
      });
      await video.play();
      setStatus("ready");
    } catch (e) {
      if (cameraRequestRef.current !== requestId) return;
      stopCamera();
      const cameraMessage = {
        NotAllowedError: "카메라 권한이 차단되었습니다. 주소창의 카메라 권한을 허용해주세요.",
        NotFoundError: "사용할 수 있는 카메라를 찾지 못했습니다.",
        NotReadableError: "다른 앱이 카메라를 사용 중입니다. 다른 앱을 닫고 다시 시도해주세요.",
        AbortError: "카메라 연결이 중단되었습니다. 다시 시도해주세요.",
      }[e?.name];
      setError(cameraMessage || e?.message || "카메라를 열 수 없습니다. 브라우저 권한을 확인해주세요.");
      setStatus("error");
    }
  }, [stopCamera]);

  useEffect(() => {
    startCamera();
    return stopCamera; // 화면을 벗어나면 카메라를 반드시 끈다
  }, [startCamera, stopCamera]);

  async function shoot() {
    const video = videoRef.current;
    if (status !== "ready" || !video || !video.videoWidth || !video.videoHeight) {
      setError("카메라 영상이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요.");
      return;
    }
    setStatus("working");
    setError(null);
    try {
      // 정사각형으로 가운데를 잘라 640px 로 줄인다(전송량·비용을 줄이려고).
      const side = Math.min(video.videoWidth, video.videoHeight);
      const canvas = document.createElement("canvas");
      canvas.width = 640;
      canvas.height = 640;
      canvas
        .getContext("2d")
        .drawImage(
          video,
          (video.videoWidth - side) / 2,
          (video.videoHeight - side) / 2,
          side,
          side,
          0,
          0,
          640,
          640
        );
      const image = canvas.toDataURL("image/jpeg", 0.85);
      stopCamera(); // 찍는 즉시 카메라를 끈다

      // 다른 API 호출과 같은 주소 규칙을 쓴다. 기본값을 localhost로 두면 휴대폰이나
      // 외부 터널에서는 사용자 기기 자신을 가리켜 요청이 실패한다.
      const base = import.meta.env.VITE_API_BASE || "/api";
      const res = await fetch(`${base}/avatar/from-photo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image, options: buildOptions() }),
      });
      if (!res.ok) {
        let detail = `분석 실패 (${res.status})`;
        try {
          const body = await res.json();
          if (body.detail) detail = body.detail;
        } catch {
          /* 본문이 JSON 이 아니면 상태코드만 */
        }
        throw new Error(detail);
      }
      const { config, face_visible: faceVisible } = await res.json();
      if (faceVisible === false) {
        // 얼굴이 제대로 안 잡힌 결과를 적용하면 엉뚱한 아바타가 된다. 다시 찍게 한다.
        setError("얼굴이 잘 안 보여요. 밝은 곳에서 얼굴을 원 안에 맞춰 다시 찍어주세요.");
        setStatus("error");
        return;
      }
      setShot(image);
      setResult(config);
      setStatus("review"); // 바로 적용하지 않는다
    } catch (e) {
      setError(e.message);
      setStatus("error");
    }
  }

  function discard() {
    setShot(null);
    setResult(null);
  }

  function apply() {
    onResult?.(result);
    discard();
  }

  function retake() {
    discard();
    startCamera();
  }

  function close() {
    stopCamera();
    discard();
    onClose?.();
  }

  const same = (a, b) =>
    typeof a === "object" || typeof b === "object" ? JSON.stringify(a) === JSON.stringify(b) : a === b;
  const changed = result
    ? Object.keys(result).filter((k) => FIELD_LABELS[k] && !same(result[k], current?.[k]))
    : [];

  return (
    <div className="mt-3 rounded-2xl border border-violet-400/20 bg-[#0B1423] p-3">
      <div className="flex items-center justify-between">
        <strong className="text-[12px] text-ink">카메라로 맞추기</strong>
        <button type="button" onClick={close} className="tap text-[11px] text-sub">
          닫기
        </button>
      </div>

      {status === "review" ? (
        <>
          <p className="mt-2 text-[11px] text-sub">이렇게 시작해볼까요?</p>
          <div className="mt-2 flex items-center justify-center gap-3">
            <figure className="m-0 text-center">
              <img
                src={shot}
                alt="방금 찍은 사진"
                className="h-[104px] w-[104px] rounded-xl object-cover"
                style={{ transform: "scaleX(-1)" }}
              />
              <figcaption className="mt-1 text-[9px] text-mut">사진</figcaption>
            </figure>
            <span className="text-[16px] text-mut">→</span>
            <figure className="m-0 text-center">
              <Avatar config={{ ...current, ...result }} size={104} ring={false} />
              <figcaption className="mt-1 text-[9px] text-mut">아바타</figcaption>
            </figure>
          </div>

          <p className="mt-2 text-[10px] leading-relaxed text-mut">
            {changed.length
              ? `바뀌는 항목 ${changed.length}개 · ${changed.map((k) => FIELD_LABELS[k]).join(" · ")}`
              : "바뀌는 항목이 없습니다."}
            <br />
            선택지가 정해져 있어서 똑같이 생기진 않습니다. 적용한 뒤 화살표로 고치시면 됩니다.
          </p>

          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={apply}
              className="tap flex-1 rounded-xl border border-violet-400/25 bg-violet-500/15 py-2.5 text-[12px] font-semibold text-violet-200"
            >
              적용하기
            </button>
            <button
              type="button"
              onClick={retake}
              className="tap rounded-xl border border-white/10 bg-white/[.04] px-3 py-2.5 text-[12px] text-sub"
            >
              다시 찍기
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="relative mt-2 overflow-hidden rounded-xl bg-black/40">
            <video
              ref={videoRef}
              playsInline
              muted
              className="block h-[260px] w-full object-cover"
              style={{ transform: "scaleX(-1)" }} // 거울처럼 보이게
            />
            {/* 얼굴 맞추는 가이드. 이 안에 얼굴을 채우면 잘린 사진이 줄어든다. */}
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="h-[200px] w-[155px] rounded-[50%] border-2 border-dashed border-violet-300/60 shadow-[0_0_0_9999px_rgba(0,0,0,.35)]" />
            </div>
            <p className="pointer-events-none absolute inset-x-0 bottom-1.5 text-center text-[10px] text-white/80">
              얼굴을 원 안에 맞춰주세요
            </p>
          </div>

          {error && <p className="mt-2 text-[11px] text-danger">{error}</p>}

          <button
            type="button"
            onClick={status === "error" ? startCamera : shoot}
            disabled={status === "starting" || status === "working"}
            className="tap mt-2 w-full rounded-xl border border-violet-400/25 bg-violet-500/15 py-2.5 text-[12px] font-semibold text-violet-200 disabled:opacity-50"
          >
            {status === "starting"
              ? "카메라 준비 중…"
              : status === "working"
                ? "분석 중…"
                : status === "error"
                  ? "다시 시도"
                  : "이 얼굴로 맞추기"}
          </button>

          <p className="mt-2 text-[10px] leading-relaxed text-mut">
            사진은 저장되지 않습니다.
            <br />
          </p>
        </>
      )}
    </div>
  );
}
